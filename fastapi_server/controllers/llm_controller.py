"""
LLM Controller for handling AI-powered trading analysis through API endpoints.

This controller provides REST API endpoints for LLM-based trading decisions,
separating the LLM logic from Airflow orchestration.
"""

import logging
from typing import Dict

from fastapi import APIRouter
from llm_strategy import LLMTradingStrategy
from pydantic import BaseModel

logger = logging.getLogger("api_logger")

router = APIRouter(prefix="/v1/llm", tags=["LLM Trading Analysis"])


class LLMAnalysisRequest(BaseModel):
    """Request model for LLM analysis."""
    
    stock_symbol: str
    prophet_diff_rate: float
    statistics: Dict
    current_price: float
    period_days: int = 30


class LLMAnalysisResponse(BaseModel):
    """Response model for LLM analysis."""
    
    decision: str
    reasoning: str
    confidence: float
    enabled: bool


@router.post("/analyze", response_model=LLMAnalysisResponse)
def analyze_stock_with_llm(request: LLMAnalysisRequest):
    """
    Analyze stock using LLM and provide trading decision with reasoning.
    
    This endpoint performs AI-powered analysis combining technical indicators
    with market context to provide trading recommendations.
    
    Args:
        request: LLMAnalysisRequest containing stock data and analysis parameters
        
    Returns:
        LLMAnalysisResponse: Trading decision, reasoning, confidence score, and availability status
    """
    logger.info(
        f"LLM analysis requested for {request.stock_symbol}", 
        extra={"endpoint_name": "analyze_stock_with_llm"}
    )
    
    try:
        # Initialize LLM strategy
        strategy = LLMTradingStrategy()
        
        if not strategy.is_enabled():
            logger.warning(
                "LLM strategy not available", 
                extra={"endpoint_name": "analyze_stock_with_llm"}
            )
            return LLMAnalysisResponse(
                decision="HOLD",
                reasoning="LLM strategy not available",
                confidence=0.0,
                enabled=False
            )
        
        # Perform LLM analysis
        decision, reasoning, confidence = strategy.analyze_stock_and_decide(
            stock_symbol=request.stock_symbol,
            prophet_diff_rate=request.prophet_diff_rate,
            statistics=request.statistics,
            current_price=request.current_price,
            period_days=request.period_days
        )
        
        logger.info(
            f"LLM analysis completed for {request.stock_symbol}: {decision} (confidence: {confidence})",
            extra={"endpoint_name": "analyze_stock_with_llm"}
        )
        
        return LLMAnalysisResponse(
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            enabled=True
        )
        
    except Exception as e:
        logger.error(
            f"Error in LLM analysis for {request.stock_symbol}: {e}",
            extra={"endpoint_name": "analyze_stock_with_llm"}
        )
        return LLMAnalysisResponse(
            decision="HOLD",
            reasoning=f"LLM analysis failed: {str(e)}",
            confidence=0.0,
            enabled=False
        )


@router.get("/health")
def check_llm_health():
    """
    Check if LLM service is available and healthy.
    
    Returns:
        Dict: Health status information
    """
    try:
        strategy = LLMTradingStrategy()
        is_available = strategy.is_enabled()
        
        return {
            "status": "healthy" if is_available else "unavailable",
            "enabled": is_available,
            "message": "LLM service is ready" if is_available else "LLM service is not configured"
        }
    except Exception as e:
        logger.error(f"Error checking LLM health: {e}", extra={"endpoint_name": "check_llm_health"})
        return {
            "status": "error",
            "enabled": False,
            "message": f"LLM health check failed: {str(e)}"
        }