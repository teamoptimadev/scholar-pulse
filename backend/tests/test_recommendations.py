from app.ml.model_loader import model_loader
from app.ml.risk_engine import get_top_factors, predict_risk
from app.services.recommendation_service import (
    _LIMITED_DATA_MESSAGE,
    _RECOMMENDATIONS,
    generate_recommendations,
)


def test_none_options_preserve_previous_recommendation_order():
    feature_sets = [
        {"attendance_percentage": 60, "previous_cgpa": 5.5},
        {"backlog_count": 1, "study_hours_per_week": 12, "CA_mark": 40},
        {"performance_trend": "DECLINING", "MID_mark": 45},
    ]
    expected = [
        [
            _RECOMMENDATIONS["low_attendance"],
            _RECOMMENDATIONS["low_cgpa"],
        ],
        [
            _RECOMMENDATIONS["backlogs"],
            _RECOMMENDATIONS["low_study_hours"],
            _RECOMMENDATIONS["low_ca"],
        ],
        [
            _RECOMMENDATIONS["declining_performance"],
            _RECOMMENDATIONS["low_mid"],
        ],
    ]

    assert [
        generate_recommendations(features)
        for features in feature_sets
    ] == expected


def test_recommendations_follow_top_factor_order():
    features = {"attendance_percentage": 60, "previous_cgpa": 5.5}
    attendance_first = [
        {"feature": "attendance_percentage", "is_missing": False},
        {"feature": "previous_cgpa", "is_missing": False},
    ]
    cgpa_first = list(reversed(attendance_first))

    assert generate_recommendations(features, attendance_first) == [
        _RECOMMENDATIONS["low_attendance"],
        _RECOMMENDATIONS["low_cgpa"],
    ]
    assert generate_recommendations(features, cgpa_first) == [
        _RECOMMENDATIONS["low_cgpa"],
        _RECOMMENDATIONS["low_attendance"],
    ]


def test_top_factors_do_not_add_or_drop_recommendations():
    features = {
        "attendance_percentage": 60,
        "previous_cgpa": 5.5,
        "backlog_count": 2,
        "CA_mark": 40,
    }
    baseline = generate_recommendations(features)
    with_top_factors = generate_recommendations(
        features,
        top_factors=[
            {"feature": "attendance_percentage", "is_missing": False},
            {"feature": "unknown", "is_missing": False},
        ],
    )

    assert sorted(with_top_factors) == sorted(baseline)


def test_limited_data_message_is_last_below_half_completeness():
    features = {"attendance_percentage": 60}

    for completeness in (0.0, 0.49):
        recommendations = generate_recommendations(
            features, data_completeness=completeness
        )
        assert recommendations[-1] == _LIMITED_DATA_MESSAGE
        assert recommendations.count(_LIMITED_DATA_MESSAGE) == 1

    for completeness in (0.5, 1.0):
        assert _LIMITED_DATA_MESSAGE not in generate_recommendations(
            features, data_completeness=completeness
        )


def test_fresher_with_no_features_gets_only_limited_data_message():
    features = {feature: None for feature in model_loader.risk_config["feature_weights"]}

    assert generate_recommendations(features, data_completeness=0.0) == [
        _LIMITED_DATA_MESSAGE
    ]


def test_predict_risk_recommendations_follow_contribution_order():
    features = {
        "attendance_percentage": 60,
        "previous_cgpa": None,
        "backlog_count": 2,
        "current_failed_courses": None,
        "low_performance_course_count": None,
        "study_hours_per_week": None,
        "assignment_completion_percentage": None,
        "performance_trend": None,
    }

    risk = predict_risk(features)
    top_factors = get_top_factors(features, model_loader.risk_config)
    expected_keys = [
        {
            "attendance_percentage": "low_attendance",
            "backlog_count": "backlogs",
        }[factor["feature"]]
        for factor in top_factors
        if factor["feature"] in {"attendance_percentage", "backlog_count"}
    ]
    expected = [_RECOMMENDATIONS[key] for key in expected_keys]
    if risk["data_completeness"] < 0.5:
        expected.append(_LIMITED_DATA_MESSAGE)

    assert risk["recommendations"] == expected
