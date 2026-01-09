import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import threading
import numpy as np


class ChannelMonitorWeb:
    def __init__(self, host="127.0.0.1", port=8051):
        print("Starting display..")
        self.host = host
        self.port = port

        # Internal storage of arrays
        self.data_192 = None
        self.data_36 = None
        self.charge_samples = {ch: [] for ch in range(193)}
        self.light_samples = {ch: [] for ch in range(64)}

        # Dash app
        self.app = dash.Dash(__name__)

        # Layout: two groups of graphs
        self.app.layout = html.Div([
            html.H1("Channel Monitor"),

            html.H2("Charge Channels"),
            dcc.Graph(id="plot-192-event"),
            dcc.Graph(id="plot-192-main"),
            dcc.Graph(id="plot-192-stddev"),
            dcc.Graph(id="plot-192-hits"),

            html.H2("Light Channels"),
            dcc.Graph(id="plot-36-event"),
            dcc.Graph(id="plot-36-main"),
            dcc.Graph(id="plot-36-stddev"),
            dcc.Graph(id="plot-36-hits"),

            # Timer triggers auto-refresh every 2 second
            dcc.Interval(id="update-interval", interval=2000, n_intervals=0)
        ])

        print([c.id for c in self.app.layout.children if isinstance(c, dcc.Graph)])

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

    def update_samples(self, sample, channel, is_charge):
        if is_charge:
            self.charge_samples[channel] = list(sample)
        else:
            self.light_samples[channel] = list(sample)

    # ------------------------------------------------------------
    # Graph builder (baseline + RMS together; hits alone)
    # ------------------------------------------------------------
    def _build_main_plot(self, baseline, std_dev):
        n = len(baseline)

        fig = go.Figure()
        fig.add_bar(name="Baseline", x=list(range(n)), y=baseline,
                    error_y=dict(
                                    type='data',
                                    array=std_dev, # The array of error bar sizes
                                    visible=True # Makes the error bars visible
                                ))
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

    def _build_stddev_plot(self, stddev):
        n = len(stddev)
        fig = go.Figure()
        fig.add_bar(name="StdDev", x=list(range(n)), y=stddev)
        fig.update_layout(xaxis_title="Channel",
                          yaxis_title="StdDev [ADC]")
        return fig

    def _build_event_plot(self, samples):

        fig = go.Figure()
        for ch in samples:
            n = len(ch)
            if n < 1: # if no data, skip
                continue
            # Create a Scatter trace
            scatter_trace = go.Scatter(x=list(range(n)), y=ch, mode='lines+markers')
            fig.update_layout(yaxis_range=[0, 4100])
            fig.add_trace(scatter_trace)
            # fig.add_bar(name="Channels", x=list(range(n)), y=ch)
        fig.update_layout(xaxis_title="Sample",
                          yaxis_title="ADC")
        return fig

    # ------------------------------------------------------------
    # Dash Callbacks — refresh page once per second
    # ------------------------------------------------------------
    def _register_callbacks(self):
        @self.app.callback(
            [
                Output("plot-192-event", "figure"),
                Output("plot-192-main", "figure"),
                Output("plot-192-stddev", "figure"),
                Output("plot-192-hits", "figure"),
                Output("plot-36-event", "figure"),
                Output("plot-36-main", "figure"),
                Output("plot-36-stddev", "figure"),
                Output("plot-36-hits", "figure"),
            ],
            [Input("update-interval", "n_intervals")]
        )
        def update_graphs(_):
            # If we have no data yet, draw placeholders
            if self.data_192 is None or self.data_36 is None:
                empty = go.Figure()
                return empty, empty, empty, empty, empty, empty, empty, empty

            b192, r192, h192 = self.data_192
            b36, r36, h36 = self.data_36

            return (
                self._build_event_plot(self.charge_samples),
                self._build_main_plot(b192, r192),
                self._build_stddev_plot(r192),
                self._build_hits_plot(h192),
                self._build_event_plot(self.light_samples),
                self._build_main_plot(b36, r36),
                self._build_stddev_plot(r36),
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

