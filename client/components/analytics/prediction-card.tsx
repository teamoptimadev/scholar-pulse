import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RiskBadge } from "@/components/analytics/risk-badge";
import type { AllPredictions } from "@/types/prediction";

interface PredictionCardProps {
  predictions: AllPredictions;
  showDetails?: boolean;
}

const FACTOR_LABELS: Record<string, string> = {
  attendance_percentage: "Attendance",
  previous_cgpa: "Previous CGPA",
  backlog_count: "Backlogs",
  current_failed_courses: "Currently failing courses",
  low_performance_course_count: "Low-performance courses",
  study_hours_per_week: "Weekly study hours",
  assignment_completion_percentage: "Assignment completion",
  performance_trend: "Performance trend",
};

const LIMITED_HISTORY_MESSAGE =
  "This assessment uses limited recorded data and may change as more records are added.";

export function PredictionCard({
  predictions,
  showDetails = false,
}: PredictionCardProps) {
  const { performance, pass_fail, risk } = predictions;
  const topFactors = risk.top_factors ?? [];
  const hasTopFactors = topFactors.length > 0;
  const isLimitedHistory = (risk.data_completeness ?? 1.0) < 0.5;
  const isCaOnly =
    performance.model_variant === "ca_only" ||
    pass_fail.model_variant === "ca_only";

  const factorLabel = (feature: string) => FACTOR_LABELS[feature] ?? feature;

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Predicted End-Term Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">
            {Math.round(performance.predicted_end_marks)} / 100
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            ML-powered academic prediction
          </p>
          {isCaOnly && (
            <p className="text-xs text-muted-foreground mt-1">
              Estimated from internal assessment marks only (mid-term not
              recorded)
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Likelihood of Passing
          </CardTitle>
        </CardHeader>
        <CardContent>
          {showDetails ? (
            <div className="text-3xl font-bold">
              {Math.round(pass_fail.pass_probability * 100)}%
            </div>
          ) : (
            <div className="text-3xl font-bold">{pass_fail.prediction}</div>
          )}
          {showDetails && (
            <p className="text-xs text-muted-foreground mt-1">
              Predicted: {pass_fail.prediction}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Academic Risk
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <RiskBadge level={risk.risk_level} />
            {isLimitedHistory && (
              <Badge variant="outline">Limited history</Badge>
            )}
            <span className="text-2xl font-bold">{risk.risk_score}</span>
          </div>
          {isLimitedHistory && (
            <p className="text-xs text-muted-foreground mt-2">
              {LIMITED_HISTORY_MESSAGE}
            </p>
          )}
          {hasTopFactors ? (
            <ul className="text-xs text-muted-foreground mt-2 space-y-1">
              {topFactors.slice(0, 3).map((factor) => (
                <li key={factor.feature}>
                  {showDetails ? (
                    <>
                      <span>{factorLabel(factor.feature)}</span>
                      <span className="mx-1">
                        +{factor.contribution} pts
                      </span>
                      <span>
                        {factor.is_missing || factor.value === null
                          ? "not recorded"
                          : factor.value}
                      </span>
                    </>
                  ) : (
                    <>
                      {factorLabel(factor.feature)}
                      {factor.is_missing && " (not recorded yet)"}
                    </>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            risk.risk_factors.length > 0 && (
              <ul className="text-xs text-muted-foreground mt-2 space-y-1">
                {risk.risk_factors.slice(0, 3).map((f) => (
                  <li key={f}>• {f}</li>
                ))}
              </ul>
            )
          )}
        </CardContent>
      </Card>
    </div>
  );
}
