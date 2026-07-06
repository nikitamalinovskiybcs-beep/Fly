"""Firebase Firestore client — real-time state for live UI updates.

Free tier: 1GB storage, 50K reads/day, 20K writes/day.
Graceful degradation: if no credentials, all operations are no-ops.

Environment variables:
    FIREBASE_CREDENTIALS={"type":"service_account",...}
"""

import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class FirebaseStorage:
    """Real-time state storage via Firebase Firestore.

    Collections:
        live_portfolio — current positions + cash (1 document)
        alerts — active alerts (real-time listener)
        agent_status — status of each agent (online/offline/error)
        market_regime — current detected regime
    """

    def __init__(self, credentials_json: str = "") -> None:
        self._client = None
        self._enabled = False

        if not credentials_json:
            logger.info("Firebase not configured, real-time features disabled")
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            cred_dict = json.loads(credentials_json)
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            self._client = firestore.client()
            self._enabled = True
            logger.info("Firebase Firestore connected")
        except ImportError:
            logger.info("firebase-admin not installed, Firebase disabled")
        except Exception as exc:
            logger.warning("Firebase init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        """Whether Firebase is available."""
        return self._enabled

    def update_portfolio(self, portfolio: dict) -> bool:
        """Update live portfolio document.

        Args:
            portfolio: Portfolio state dict (cash, positions, total_value).

        Returns:
            True if updated successfully.
        """
        if not self._enabled:
            return False
        try:
            doc = {**portfolio, "updated_at": datetime.now().isoformat()}
            self._client.collection("live_portfolio").document("current").set(doc)
            return True
        except Exception as exc:
            logger.warning("Firebase portfolio update failed: %s", exc)
            return False

    def get_portfolio(self) -> Optional[dict]:
        """Get current live portfolio.

        Returns:
            Portfolio dict or None.
        """
        if not self._enabled:
            return None
        try:
            doc = self._client.collection("live_portfolio").document("current").get()
            return doc.to_dict() if doc.exists else None
        except Exception as exc:
            logger.warning("Firebase portfolio read failed: %s", exc)
            return None

    def add_alert(self, alert: dict) -> Optional[str]:
        """Add a real-time alert.

        Args:
            alert: Alert dict (level, type, message, ticker).

        Returns:
            Document ID or None.
        """
        if not self._enabled:
            return None
        try:
            alert["timestamp"] = datetime.now().isoformat()
            alert["dismissed"] = False
            _, doc_ref = self._client.collection("alerts").add(alert)
            return doc_ref.id
        except Exception as exc:
            logger.warning("Firebase add alert failed: %s", exc)
            return None

    def get_active_alerts(self) -> list[dict]:
        """Get all non-dismissed alerts.

        Returns:
            List of alert dicts.
        """
        if not self._enabled:
            return []
        try:
            docs = (
                self._client.collection("alerts")
                .where("dismissed", "==", False)
                .order_by("timestamp")
                .stream()
            )
            return [{"id": d.id, **d.to_dict()} for d in docs]
        except Exception as exc:
            logger.warning("Firebase get alerts failed: %s", exc)
            return []

    def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss an alert by ID.

        Args:
            alert_id: Firestore document ID.

        Returns:
            True if dismissed.
        """
        if not self._enabled:
            return False
        try:
            self._client.collection("alerts").document(alert_id).update({"dismissed": True})
            return True
        except Exception as exc:
            logger.warning("Firebase dismiss alert failed: %s", exc)
            return False

    def set_agent_status(self, agent_name: str, status: dict) -> bool:
        """Set status for an agent.

        Args:
            agent_name: Agent identifier.
            status: Status dict (state, last_run, error).

        Returns:
            True if set.
        """
        if not self._enabled:
            return False
        try:
            status["updated_at"] = datetime.now().isoformat()
            self._client.collection("agent_status").document(agent_name).set(status)
            return True
        except Exception as exc:
            logger.warning("Firebase agent status failed: %s", exc)
            return False

    def get_all_agent_statuses(self) -> dict[str, dict]:
        """Get statuses for all agents.

        Returns:
            Dict of agent_name -> status_dict.
        """
        if not self._enabled:
            return {}
        try:
            docs = self._client.collection("agent_status").stream()
            return {d.id: d.to_dict() for d in docs}
        except Exception as exc:
            logger.warning("Firebase get agent statuses failed: %s", exc)
            return {}

    def set_regime(self, regime: str, confidence: float) -> bool:
        """Set current market regime.

        Args:
            regime: Regime name (bull/bear/sideways).
            confidence: Detection confidence 0-1.

        Returns:
            True if set.
        """
        if not self._enabled:
            return False
        try:
            self._client.collection("market_regime").document("current").set({
                "regime": regime,
                "confidence": confidence,
                "updated_at": datetime.now().isoformat(),
            })
            return True
        except Exception as exc:
            logger.warning("Firebase set regime failed: %s", exc)
            return False

    def get_regime(self) -> Optional[dict]:
        """Get current market regime.

        Returns:
            Regime dict or None.
        """
        if not self._enabled:
            return None
        try:
            doc = self._client.collection("market_regime").document("current").get()
            return doc.to_dict() if doc.exists else None
        except Exception as exc:
            logger.warning("Firebase get regime failed: %s", exc)
            return None
