import streamlit as st
import pandas as pd
import math
from matplotlib.patches import Ellipse, Circle
import matplotlib.pyplot as plt

st.title("Sociogram")

uploaded_file = st.file_uploader("Upload Excel-fil", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Find valgkolonner
    choice_cols = [c for c in df.columns if c.lower().startswith("valg")]

    # Rens data
    df["elev"] = df["elev"].astype(str).str.strip()
    for c in choice_cols:
        df[c] = df[c].astype(str).str.strip()

    # === Tjek for manglende valg ===
    missing = df[df[choice_cols].isna().any(axis=1)]
    if not missing.empty:
        st.error("Nogle elever mangler valg. Ret venligst filen.")
        st.stop()

    # === Tjek for selvvalg ===
    self_ref = []
    for _, row in df.iterrows():
        if row["elev"] in row[choice_cols].values:
            self_ref.append(row["elev"])
    if self_ref:
        st.error("Følgende elever peger på sig selv: " + ", ".join(sorted(set(self_ref))))
        st.stop()

    # === Find mistænkelige navne (valgt, men ikke selv i elevkolonnen) ===
    elevliste = set(df["elev"].str.lower())
    valgte = set()

    for c in choice_cols:
        valgte.update(df[c].str.lower())

    mistænkelige = valgte - elevliste

    if mistænkelige:
        fejl_navn = ", ".join(sorted(mistænkelige))
        st.warning(
            f"Advarsel: En eller flere peger på {fejl_navn}, men denne/disse har ikke peget på nogle. "
            "Tjek om der er stavefejl eller manglende elev i første kolonne."
        )

    # === Korrekt tællelogik (gammel metode, men forbedret) ===
    all_names = pd.concat(
        [df["elev"]] +
        [df[c] for c in choice_cols]
    ).astype(str).str.strip()

    contacts_count = all_names.value_counts().to_dict()

    # Sortér efter antal (mest populære først)
    names = sorted(
        contacts_count.keys(),
        key=lambda name: contacts_count[name],
        reverse=True
    )

    # === Layoutfunktioner ===
    def layout_circle(names):
        n = len(names)
        positions = {}
        for i, name in enumerate(names):
            angle = 2 * math.pi * i / n - math.pi/2
            positions[name] = (0.5 + 0.35 * math.cos(angle),
                               0.5 + 0.35 * math.sin(angle))
        return positions

    def layout_grid(names):
        cols = 5
        positions = {}
        for i, name in enumerate(names):
            row = i // cols
            col = i % cols
            positions[name] = (0.15 + col * 0.17, 0.8 - row * 0.15)
        return positions

    layout_valg = st.radio("Vælg layout", ["Cirkel-layout", "Grid-layout"])
    positions = layout_circle(names) if layout_valg == "Cirkel-layout" else layout_grid(names)

    # === Farvefunktion ===
    def farve(n):
        if n == 1:
            return "black"
        elif n == 2:
            return "purple"
        elif n == 3:
            return "darkorange"
        elif n == 4:
            return "goldenrod"
        elif n == 5:
            return "forestgreen"
        else:
            return "royalblue"

    # === Tegn sociogram ===
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    node_width = 0.12
    node_height = 0.06

    # Ovale noder
    for elev in names:
        x, y = positions[elev]
        ax.add_patch(
            Ellipse(
                (x, y),
                width=node_width,
                height=node_height,
                fill=False,
                edgecolor=farve(contacts_count[elev]),
                linewidth=2.5
            )
        )
        ax.text(x, y, elev, ha="center", va="center", fontsize=14)

    # Markér mistænkelige elever
    for elev in names:
        if elev.lower() in mistænkelige:
            x, y = positions[elev]
            ax.add_patch(
                Ellipse(
                    (x, y),
                    width=node_width * 1.6,
                    height=node_height * 1.6,
                    fill=False,
                    edgecolor="red",
                    linewidth=4,
                    linestyle="--",
                    zorder=50
                )
            )

    # Pile
    for _, row in df.iterrows():
        fra = row["elev"]
        for c in choice_cols:
            til = row[c]
            if fra in positions and til in positions:
                x1, y1 = positions[fra]
                x2, y2 = positions[til]
                ax.annotate(
                    "",
                    xy=(x2, y2),
                    xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=1.5)
                )

    # === Farveforklaring i to rækker ===
    legend_items = [
        ("Ingen peger på", "black"),
        ("1 peger på", "purple"),
        ("2 peger på", "darkorange"),
        ("3 peger på", "goldenrod"),
        ("4 peger på", "forestgreen"),
        ("5+ peger på", "royalblue"),
    ]

    items_per_row = 3
    circle_r = 0.015
    row_spacing = 0.06
    base_y = -0.02
    base_x = 0.10
    spacing_x = 0.28

    for i, (label, color) in enumerate(legend_items):
        row = i // items_per_row
        col = i % items_per_row

        x = base_x + col * spacing_x
        y = base_y - row * row_spacing

        ax.add_patch(
            Circle(
                (x, y),
                circle_r,
                fill=False,
                edgecolor=color,
                linewidth=2.5,
                transform=ax.transAxes,
                zorder=999,
                clip_on=False
            )
        )

        ax.text(
            x + 0.03,
            y,
            label,
            va="center",
            fontsize=10,
            transform=ax.transAxes,
            zorder=999,
            clip_on=False
        )

    st.pyplot(fig)
