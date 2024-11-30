import fire
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from pathlib import Path


def plot_environmental_data(
    csv_path: str,
    output_path: str = None,
    style: str = "whitegrid",
    color_palette: str = "husl",
    dpi: int = 300,
):
    """
    Create environmental data plots from CSV and optionally save to file.
    """
    sns.set_theme(style=style)
    sns.set_palette(color_palette)

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig = plt.figure(figsize=(15, 10), dpi=dpi)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3)

    # Temperature and Humidity plot
    ax1 = fig.add_subplot(gs[0])
    line1 = ax1.plot(
        df["timestamp"], df["temperature"], linewidth=2, label="Temperature (°C)"
    )
    ax1.fill_between(df["timestamp"], df["temperature"], alpha=0.2)

    ax1_twin = ax1.twinx()
    line2 = ax1_twin.plot(
        df["timestamp"],
        df["humidity"],
        linewidth=2,
        label="Humidity (%)",
        color="#2ecc71",
    )
    ax1_twin.fill_between(df["timestamp"], df["humidity"], alpha=0.1, color="#2ecc71")

    ax1.set_title("Temperature & Humidity Over Time", fontsize=16, pad=20)
    ax1.set_xlabel("Time", fontsize=12)
    ax1.set_ylabel("Temperature (°C)", fontsize=12, color=line1[0].get_color())
    ax1_twin.set_ylabel("Humidity (%)", fontsize=12, color=line2[0].get_color())

    lines = line1 + line2
    ax1.legend(
        lines,
        [l.get_label() for l in lines],
        loc="upper left",
        frameon=True,
        fancybox=True,
        shadow=True,
    )

    # Air Quality plot
    ax2 = fig.add_subplot(gs[1])
    colors = ["#e74c3c", "#3498db", "#f1c40f"]
    for data, label, color in zip(
        [df["co2"], df["tvoc"], df["eco2"]], ["CO₂ (ppm)", "TVOC (ppb)", "eCO₂"], colors
    ):
        line = ax2.plot(df["timestamp"], data, linewidth=2, label=label, color=color)
        ax2.fill_between(df["timestamp"], data, alpha=0.1, color=color)

    ax2.set_title("Air Quality Metrics Over Time", fontsize=16, pad=20)
    ax2.set_xlabel("Time", fontsize=12)
    ax2.set_ylabel("Value", fontsize=12)
    ax2.legend(loc="upper left", frameon=True, fancybox=True, shadow=True)

    for ax in [ax1, ax2]:
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="x", rotation=45)

    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle("Environmental Monitoring Dashboard", fontsize=20, y=1.02)

    if output_path:
        plt.savefig(output_path, bbox_inches="tight", dpi=dpi)
        print(f"Plot saved to {output_path}")
    else:
        plt.show()


if __name__ == "__main__":
    fire.Fire(plot_environmental_data)

