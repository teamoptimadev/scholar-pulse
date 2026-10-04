"""Prediction request/response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class PerformanceFeatures(BaseModel):
    CA_mark: float = Field(..., ge=0, le=100)
    MID_mark: float = Field(..., ge=0, le=100)
    attendance_percentage: float = Field(..., ge=0, le=100)
    study_hours_per_week: float = Field(..., ge=0, le=60)
    assignment_completion_pct: float = Field(..., ge=0, le=100)
    previous_sgpa: float = Field(..., ge=0, le=10)
    previous_cgpa: float = Field(..., ge=0, le=10)
    backlog_count: int = Field(..., ge=0)
    course_credits: int = Field(..., ge=1, le=6)
    course_type: str = Field(default="THEORY")
    branch: str = Field(default="CSE")
    semester: int = Field(..., ge=1, le=8)


class PassFailFeatures(BaseModel):
    CA_mark: float = Field(..., ge=0, le=100)
    MID_mark: float = Field(..., ge=0, le=100)
    attendance_percentage: float = Field(..., ge=0, le=100)
    study_hours_per_week: float = Field(..., ge=0, le=60)
    assignment_completion_pct: float = Field(..., ge=0, le=100)
    previous_sgpa: float = Field(..., ge=0, le=10)
    previous_cgpa: float = Field(..., ge=0, le=10)
    backlog_count: int = Field(..., ge=0)
    course_credits: int = Field(..., ge=1, le=6)
    branch: str = Field(default="CSE")
    semester: int = Field(..., ge=1, le=8)


class RiskFeatures(BaseModel):
    attendance_percentage: float | None = Field(default=None, ge=0, le=100)
    previous_cgpa: float | None = Field(default=None, ge=0, le=10)
    backlog_count: int | None = Field(default=None, ge=0)
    current_failed_courses: int | None = Field(default=None, ge=0)
    low_performance_course_count: int | None = Field(default=None, ge=0)
    study_hours_per_week: float | None = Field(default=None, ge=0, le=60)
    assignment_completion_percentage: float | None = Field(default=None, ge=0, le=100)
    performance_trend: str | None = Field(default=None)


class PerformancePredictionResponse(BaseModel):
    predicted_end_marks: float


class PassFailPredictionResponse(BaseModel):
    prediction: str
    pass_probability: float
    fail_probability: float


class RiskFactor(BaseModel):
    feature: str
    contribution: float
    value: float | str | None = None
    is_missing: bool


class RiskPredictionResponse(BaseModel):
    risk_score: float
    risk_level: str
    risk_factors: list[str]
    recommendations: list[str]
    data_completeness: float = Field(default=1.0)
    top_factors: list[RiskFactor] = Field(default_factory=list)


class AllPredictionsResponse(BaseModel):
    student_id: str | None = None
    performance: PerformancePredictionResponse
    pass_fail: PassFailPredictionResponse
    risk: RiskPredictionResponse


class StudentPredictionRequest(BaseModel):
    student_id: str
    enrollment_id: str | None = None


class PredictionFeaturesRequest(BaseModel):
    """Direct feature input for predictions."""
    performance: PerformanceFeatures | None = None
    pass_fail: PassFailFeatures | None = None
    risk: RiskFeatures | None = None
    features: dict[str, Any] | None = None
