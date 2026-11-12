from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def empty_figure(message: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    figure.update_layout(template="plotly_white", height=360)
    return figure


def bar_chart(frame: pd.DataFrame, x: str, y: str, title: str) -> go.Figure:
    if frame.empty:
        return empty_figure("This metric is not available in the loaded dataset.")
    return px.bar(frame, x=x, y=y, title=title, template="plotly_white")


def line_chart(frame: pd.DataFrame, x: str, y: str, title: str) -> go.Figure:
    if frame.empty:
        return empty_figure("No populated time-series measure is available.")
    return px.line(frame, x=x, y=y, title=title, markers=True, template="plotly_white")
