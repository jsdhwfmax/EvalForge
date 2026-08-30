import pandas as pd
import plotly
import plotly.express as px


def test_supported_plotly_builds_dashboard_chart():
    frame = pd.DataFrame(
        {
            "Metric": ["Recall@K", "Correctness"],
            "Score": [0.8, 0.9],
            "Configuration": ["baseline", "candidate"],
        }
    )

    figure = px.bar(
        frame,
        x="Metric",
        y="Score",
        color="Configuration",
        barmode="group",
        range_y=[0, 1],
    )
    figure.update_layout(plot_bgcolor="white", paper_bgcolor="white")

    assert plotly.__version__.split(".", 1)[0] in {"5", "6", "7"}
    assert len(figure.data) == 2
