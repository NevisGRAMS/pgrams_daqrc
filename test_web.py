import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import threading
import numpy as np


class ChannelMonitorWeb:
    def __init__(self, host="10.44.45.96", port=8050):
        print("Starting display..")
        self.host = host
        self.port = port

        # Internal storage of arrays
        self.data_192 = None
        self.data_36 = None

        # Dash app
        self.app = dash.Dash(__name__)

        # Layout: two groups of graphs
        self.app.layout = html.Div([
            html.H1("Channel Monitor"),

            html.H2("Charge Channels"),
            dcc.Graph(id="plot-192-main"),
            dcc.Graph(id="plot-192-hits"),

            html.H2("Light Channels"),
            dcc.Graph(id="plot-36-main"),
            dcc.Graph(id="plot-36-hits"),

            # Timer triggers auto-refresh every 2 second
            dcc.Interval(id="update-interval", interval=2000, n_intervals=0)
        ])

        # Register callbacks
        self._register_callbacks()

    # ------------------------------------------------------------
    # Public API: SAME as before
    # ------------------------------------------------------------
    def update_data(self, baseline_192, rms_192, hits_192,
                          baseline_36, rms_36, hits_36):
        # Multiplied by 8 to preserve fractional part so divide here
        hits_36 = [h / 8.0 for h in hits_36]
        self.data_192 = (baseline_192[:180], rms_192[:180], hits_192[:180])
        self.data_36 = (baseline_36, rms_36, hits_36)

    # ------------------------------------------------------------
    # Graph builder (baseline + RMS together; hits alone)
    # ------------------------------------------------------------
    def _build_main_plot(self, baseline, rms):
        n = len(baseline)

        fig = go.Figure()
        fig.add_bar(name="Baseline", x=list(range(n)), y=baseline)
        fig.add_bar(name="RMS",      x=list(range(n)), y=rms)
        fig.update_layout(barmode="group",
                          xaxis_title="Channel",
                          yaxis_title="ADC")
        return fig

    def _build_hits_plot(self, hits):
        n = len(hits)

        fig = go.Figure()
        fig.add_bar(name="Hits", x=list(range(n)), y=hits)
        fig.update_layout(xaxis_title="Channel",
                          yaxis_title="Hits")
        return fig

    # ------------------------------------------------------------
    # Dash Callbacks — refresh page once per second
    # ------------------------------------------------------------
    def _register_callbacks(self):
        @self.app.callback(
            [
                Output("plot-192-main", "figure"),
                Output("plot-192-hits", "figure"),
                Output("plot-36-main", "figure"),
                Output("plot-36-hits", "figure"),
            ],
            [Input("update-interval", "n_intervals")]
        )
        def update_graphs(_):
            # If we have no data yet, draw placeholders
            if self.data_192 is None or self.data_36 is None:
                empty = go.Figure()
                return empty, empty, empty, empty

            b192, r192, h192 = self.data_192
            b36, r36, h36 = self.data_36

            return (
                self._build_main_plot(b192, r192),
                self._build_hits_plot(h192),
                self._build_main_plot(b36, r36),
                self._build_hits_plot(h36),
            )

    # ------------------------------------------------------------
    # Run webpage server in a background thread
    # ------------------------------------------------------------
    def run(self):
        thread = threading.Thread(
            target=self.app.run,
            kwargs=dict(host=self.host, port=self.port),
            daemon=True
        )
        thread.start()
        print(f"✔ ChannelMonitorWeb running at http://{self.host}:{self.port}")

