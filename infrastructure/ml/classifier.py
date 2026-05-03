"""scikit-learn ML 分类器实现。

实现 domain/routing/ml_port.py 定义的 MLClassifierPort 端口。
使用 TF-IDF + 集成分类器（Naive Bayes + Logistic Regression + Random Forest）。
"""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from domain.routing.ml_port import MLClassifierPort

logger = logging.getLogger("sivan.ml.classifier")


class SklearnMLClassifier(MLClassifierPort):
    """基于 scikit-learn 的 ML 分类器。

    使用 TF-IDF（unigram + bigram）+ VotingClassifier（NB + LR + RF）。
    支持模型持久化（pickle）。
    """

    _trained: bool = False

    def __init__(self, model_dir: str | Path | None = None) -> None:
        self._model_dir = Path(model_dir) if model_dir else None
        self._pipeline: Pipeline | None = None
        self._label_encoder: dict[str, int] = {}
        self._reverse_encoder: dict[int, str] = {}

        if self._model_dir:
            self._model_dir.mkdir(parents=True, exist_ok=True)

    # ---- 持久化 ----

    @property
    def model_path(self) -> Path | None:
        if self._model_dir:
            return self._model_dir / "ml_router_pipeline.pkl"
        return None

    @property
    def encoder_path(self) -> Path | None:
        if self._model_dir:
            return self._model_dir / "ml_router_encoder.pkl"
        return None

    def save(self) -> None:
        """保存模型和编码器到磁盘。"""
        if self._pipeline is None or self.model_path is None or self.encoder_path is None:
            return
        with open(self.model_path, "wb") as f:
            pickle.dump(self._pipeline, f)
        with open(self.encoder_path, "wb") as f:
            pickle.dump({"encoder": self._label_encoder, "reverse": self._reverse_encoder}, f)
        logger.info("ML 模型已保存到 %s", self.model_path)

    def load(self) -> bool:
        """从磁盘加载模型。成功返回 True。"""
        if self.model_path is None or self.encoder_path is None:
            return False
        if not self.model_path.exists() or not self.encoder_path.exists():
            return False
        try:
            with open(self.model_path, "rb") as f:
                self._pipeline = pickle.load(f)
            with open(self.encoder_path, "rb") as f:
                data = pickle.load(f)
                self._label_encoder = data["encoder"]
                self._reverse_encoder = data["reverse"]
            self._trained = True
            logger.info("ML 模型已从 %s 加载", self.model_path)
            return True
        except Exception as exc:
            logger.warning("ML 模型加载失败: %s", exc)
            return False

    @property
    def is_trained(self) -> bool:
        return self._trained

    # ---- 训练 ----

    def _clean_text(self, text: str) -> str:
        """文本清洗：统一小写、去除非内容字符。"""
        text = text.lower()
        # 保留中文、英文、数字、常用标点
        text = re.sub(r"[^一-鿿\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def train(self, texts: list[str], labels: list[str]) -> None:
        """训练集成分类器。

        Args:
            texts: 任务描述文本列表。
            labels: 对应的智能体标签。
        """
        cleaned = [self._clean_text(t) for t in texts]
        unique_labels = sorted(set(labels))
        self._label_encoder = {lbl: i for i, lbl in enumerate(unique_labels)}
        self._reverse_encoder = {i: lbl for lbl, i in self._label_encoder.items()}
        y = np.array([self._label_encoder[lbl] for lbl in labels])

        # 构建 pipeline: TF-IDF → VotingClassifier
        tfidf = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            sublinear_tf=True,
            min_df=1,
        )

        nb = MultinomialNB(alpha=0.1)
        lr = LogisticRegression(max_iter=1000, C=1.0)
        rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)

        ensemble = VotingClassifier(
            estimators=[("nb", nb), ("lr", lr), ("rf", rf)],
            voting="soft",
        )

        self._pipeline = Pipeline([
            ("tfidf", tfidf),
            ("ensemble", ensemble),
        ])

        self._pipeline.fit(cleaned, y)
        self._trained = True

        accuracy = self._pipeline.score(cleaned, y)
        logger.info("ML 模型训练完成，准确率: %.2f%%，样本数: %d", accuracy * 100, len(texts))

        self.save()

    # ---- 预测 ----

    def predict(self, text: str, candidates: list[str]) -> dict[str, float]:
        """预测文本属于各候选智能体的概率。

        Args:
            text: 任务描述。
            candidates: 候选智能体名称列表。

        Returns:
            智能体名称 → 概率 的映射。
        """
        if self._pipeline is None or not self._trained:
            return {}

        cleaned = self._clean_text(text)
        proba = self._pipeline.predict_proba([cleaned])[0]

        scores: dict[str, float] = {}
        for i, prob in enumerate(proba):
            agent = self._reverse_encoder.get(i)
            if agent and agent in candidates:
                scores[agent] = float(prob)

        # 对未出现在训练标签中的候选，给最低分
        known_labels = set(self._reverse_encoder.values())
        for c in candidates:
            if c not in known_labels:
                scores[c] = 0.01

        return scores

    def predict_top_k(self, text: str, candidates: list[str], k: int = 3) -> list[tuple[str, float]]:
        """预测并返回 Top-K 智能体。"""
        scores = self.predict(text, candidates)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:k]
