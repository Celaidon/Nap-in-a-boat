"""
Capability curve generator (src/eval/curve.py).
Renders capability curve (coding pass rate and scaled style score vs blend ratio t).
Plots sweep blends as lines and architectural variants as separate labeled points.
Outputs results to results/curve.png.
"""

import json
import pathlib

import matplotlib.pyplot as plt


def plot_curve(
    metrics_path: str = "results/metrics.json",
    output_png: str = "results/curve.png",
) -> str:
    path = pathlib.Path(metrics_path)
    if not path.exists():
        path = pathlib.Path("contracts/mocks/metrics.json")

    assert path.exists(), f"Metrics file not found: {metrics_path}"
    data = json.loads(path.read_text(encoding="utf-8"))

    sweep_map = {
        "sweep_000": 0.0,
        "sweep_025": 0.25,
        "sweep_050": 0.50,
        "sweep_075": 0.75,
        "sweep_100": 1.0,
    }

    sweep_pts = []
    variant_pts = []

    for b in data.get("blends", []):
        b_id = b["blend_id"]
        code_pct = b["code_pass"] * 100.0
        # Scale style score (0..10) to 0..100%
        style_pct = (b["style_score"] / 10.0) * 100.0

        if b_id in sweep_map:
            sweep_pts.append({
                "id": b_id,
                "t": sweep_map[b_id],
                "code": code_pct,
                "style": style_pct,
            })
        else:
            variant_pts.append({
                "id": b_id,
                "t": 0.5,
                "code": code_pct,
                "style": style_pct,
            })

    sweep_pts.sort(key=lambda p: p["t"])

    _fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    # Plot sweep curves
    t_vals = [p["t"] for p in sweep_pts]
    code_vals = [p["code"] for p in sweep_pts]
    style_vals = [p["style"] for p in sweep_pts]

    ax.plot(t_vals, code_vals, "o-", color="#10b981", linewidth=2.5, markersize=8, label="Coding Pass Rate (%)")
    ax.plot(t_vals, style_vals, "s-", color="#6366f1", linewidth=2.5, markersize=8, label="Writing Style Score (%)")

    # Plot variant points
    variant_colors = {"split_attn_code": "#f59e0b", "split_mlp_code": "#ec4899", "gradient_mid": "#8b5cf6"}
    for v in variant_pts:
        color = variant_colors.get(v["id"], "#ef4444")
        ax.scatter([v["t"]], [v["code"]], marker="^", s=120, color=color, zorder=5)
        ax.annotate(
            f"{v['id']} (code)",
            (v["t"], v["code"]),
            textcoords="offset points",
            xytext=(10, 5),
            fontsize=8,
            color=color,
            fontweight="semibold",
        )
        ax.scatter([v["t"]], [v["style"]], marker="v", s=120, color=color, zorder=5)
        ax.annotate(
            f"{v['id']} (style)",
            (v["t"], v["style"]),
            textcoords="offset points",
            xytext=(10, -12),
            fontsize=8,
            color=color,
            fontweight="semibold",
        )

    # Plot reference model if available
    ref = data.get("reference")
    if ref:
        ref_code = ref["code_pass"] * 100.0
        ref_style = (ref["style_score"] / 10.0) * 100.0
        ax.axhline(ref_code, linestyle="--", color="#10b981", alpha=0.5, label=f"Ref Code ({ref.get('name', 'reference')})")
        ax.axhline(ref_style, linestyle="--", color="#6366f1", alpha=0.5, label=f"Ref Style ({ref.get('name', 'reference')})")

    ax.set_title("BlendLab Capability Curve: Coding vs. Writing Style", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Blend Ratio t (0.0 = Model A Instruction, 1.0 = Model B Code)", fontsize=11, labelpad=10)
    ax.set_ylabel("Score (%)", fontsize=11, labelpad=10)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(0, 105)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="best", framealpha=0.9)

    out_p = pathlib.Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(str(out_p))
    plt.close()

    print(f"Rendered capability curve to {output_png}")
    return str(out_p)


if __name__ == "__main__":
    plot_curve()
