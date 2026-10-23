export interface PerformanceFeatures {
  CA_mark: number;
  MID_mark: number;
  attendance_percentage: number;
  study_hours_per_week: number;
  assignment_completion_pct: number;
  previous_sgpa: number;
  previous_cgpa: number;
  backlog_count: number;
  course_credits: number;
  course_type?: string;
  branch?: string;
  semester: number;
}

export interface PerformancePrediction {
  predicted_end_marks: number;
  model_variant?: "full" | "ca_only";
}

export interface PassFailPrediction {
  prediction: string;
  pass_probability: number;
  fail_probability: number;
  model_variant?: "full" | "ca_only";
}

export interface RiskFactor {
  feature: string;
  contribution: number;
  value: number | string | null;
  is_missing: boolean;
}

export interface RiskPrediction {
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  risk_factors: string[];
  recommendations: string[];
  data_completeness?: number;
  top_factors?: RiskFactor[];
}

export interface AllPredictions {
  student_id?: string;
  performance: PerformancePrediction;
  pass_fail: PassFailPrediction;
  risk: RiskPrediction;
}
