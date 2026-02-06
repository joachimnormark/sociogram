import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Ellipse
import math
from io import BytesIO
import os
from datetime import datetime
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def read_csv_smart(file, header):
    for sep in [";", ",", "\t"]:
        file.seek(0)
        try:
            return pd.read_csv(file, sep=sep, header=header)
        except Exception:
            continue
    raise ValueError("Kunne ikke læse CSV-filen.")


# === Layouts ===

def layout_circle(names):
    n = len(names)
    radius = 7
    positions = {}
    for i, name in enumerate(names):
        angle = 2 * math.pi * i / n
        positions[name] = (radius * math.cos(angle), radius * math.sin(angle))
    return positions


def layout_grid(names):
    n = len(names)
    cols = math.ceil(math.sqrt(n))
    spacing = 3
    positions = {}
    for idx, name in enumerate(names):
        r = idx // cols
        c = idx % cols
        positions[name] = (c * spacing, -r * spacing)
    return positions


# === Streamlit UI ===

st.title("Sociogram-generator")

klasse_navn = st.text_input("Indtast klassens navn (fx 7.A):")

layout_valg = st.selectbox("Vælg layout", ["Cirkel-layout", "Grid-layout"])

uploaded_file = st.file_uploader("Vælg fil", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    if ext in [".xlsx", ".xls"]:
        df_raw = pd.read_excel(uploaded_file, header=None)
    else:
        df_raw = read_csv_smart(uploaded_file, header=None)

    first_cell = str(df_raw.iloc[0, 0]).strip().lower()

    if first_cell == "elev":
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(uploaded_file, header=0)
        else:
            df = read_csv_smart(uploaded_file, header=0)
        df.columns = df.columns.str.strip().str.lower()
    else:
        df = df_raw.copy()
        df.columns = ["elev"] + [str(i) for i in range(1, df.shape[1])]
        df.columns = df.columns.str.lower()

    all_cols = list(df.columns)
    if "elev" not in all_cols:
        st.error("Kunne ikke finde en kolonne med elevnavne.")
        st.stop()

    choice_cols = [c for c in all_cols if c != "elev"]
    num_choices = len(choice_cols)

    if num_choices < 2 or num_choices > 4:
        st.error("Filen skal have 3, 4 eller 5 kolonner.")
        st.stop()

    # Rens strenge
    df["elev"] = df["elev"].astype(str).str.strip()
    for c in choice_cols:
        df[c] = df[c].astype(str).str.strip()

    # Manglende valg
    missing = []
    for _, row in df.iterrows():
        for c in choice_cols:
            if pd.isna(row[c]) or str(row[c]).strip() == "":
                missing.append(row["elev"])
                break

    if missing:
        st.error("Følgende elever mangler valg: " + ", ".join(sorted(set(missing))))
        st.stop()

    # Selvvalg
    self_ref = []
    for _, row in df.iterrows():
        elev = str(row["elev"]).strip().lower()
        for c in choice_cols:
            if elev == str(row[c]).strip().lower():
                self_ref.append(row["elev"])
                break

    if self_ref:
        st.error("Følgende elever peger på sig selv: " + ", ".join(sorted(set(self_ref))))
        st.stop()

    # Mistænkelige: valgt, men ikke selv i elevkolonnen
    elevliste_lower = set(df["elev"].str.lower())
    valgte_lower = set()
    for c in choice_cols:
        valgte_lower.update(df[c].str.lower())
    mistaenkelige_lower = valgte_lower - elevliste_lower

    if mistaenkelige_lower:
        fejl_navn = ", ".join(sorted(mistaenkelige_lower))
        st.warning(
            f"Advarsel: En eller flere peger på {fejl_navn}, men denne/disse har ikke peget på nogle. "
            "Tjek om der er stavefejl eller manglende elev i første kolonne."
        )

    # === Kontakter: antal der peger på (indgående valg) ===
    all_choices = pd.concat([df[c] for c in choice_cols]).astype(str).str.strip()
    incoming_counts = all_choices.value_counts().to_dict()

    # Alle navne: både elever og dem der kun er valgt
    all_names_unique = set(df["elev"].astype(str).str.strip()) | set(all_choices)

    # Sortér efter antal der peger på (mest populære først)
    names = sorted(
        all_names_unique,
        key=lambda name: incoming_counts.get(name, 0),
        reverse=True
    )

    # Layout
    if layout_valg == "Cirkel-layout":
        positions = layout_circle(names)
    else:
        positions = layout_grid(names)

    # Edges
    edges = []
    for _, row in df.iterrows():
        fra = row["elev"]
        for c in choice_cols:
            til = row[c]
            edges.append((fra, til))

    mutual = set()
    for a, b in edges:
        if (b, a) in edges:
            mutual.add((a, b))
            mutual.add((b, a))

    # === Tegn figur ===
    fig, ax = plt.subplots(figsize=(10, 10))

    R = 0.35  # "radius" til at klippe pile ved kanten

    def farve(n_indgaaende):
        if n_indgaaende == 0:
            return "black"
        elif n_indgaaende == 1:
            return "purple"
        elif n_indgaaende == 2:
            return "darkorange"
        elif n_indgaaende == 3:
            return "goldenrod"
        elif n_indgaaende == 4:
            return "forestgreen"
        else:
            return "royalblue"

    # Ovale noder
    for elev in names:
        x, y = positions[elev]
        n_in = incoming_counts.get(elev, 0)

        ax.add_patch(
            Ellipse(
                (x, y),
                width=R * 4.2,
                height=R * 3.2,
                fill=False,
                edgecolor=farve(n_in),
                linewidth=2
            )
        )

        ax.text(
            x,
            y,
            elev,
            ha="center",
            va="center",
            fontsize=15
        )

    # Markér mistænkelige med stor rød ellipse
    for elev in names:
        if elev.lower() in mistaenkelige_lower:
            x, y = positions[elev]
            ax.add_patch(
                Ellipse(
                    (x, y),
                    width=R * 4.2 * 1.6,
                    height=R * 3.2 * 1.6,
                    fill=False,
                    edgecolor="red",
                    linewidth=4,
                    linestyle="--",
                    zorder=50
                )
            )

    # === Pile (justeret så de stopper præcist ved kanten + grøn tykkelse = 2) ===
    for start, end in edges:
        if start not in positions or end not in positions:
            continue

        x1, y1 = positions[start]
        x2, y2 = positions[end]

        dx, dy = x2 - x1, y2 - y1
        dist = math.sqrt(dx**2 + dy**2)
        if dist == 0:
            continue

        # Start og slutpunkt justeret til ellipse-kanten
        sx = x1 + dx * (R / dist)
        sy = y1 + dy * (R / dist)
        ex = x2 - dx * (R / dist)
        ey = y2 - dy * (R / dist)

        color = "green" if (start, end) in mutual else "black"
        lw = 2 if (start, end) in mutual else 1   # <-- ændret fra 3 til 2

        ax.add_patch(
            FancyArrowPatch(
                (sx, sy),
                (ex, ey),
                arrowstyle="->",
                mutation_scale=15,
                color=color,
                linewidth=lw
            )
        )

    # Faste xlim/ylim
    if layout_valg == "Cirkel-layout":
        ax.set_xlim(-8, 8)
        ax.set_ylim(-8, 8)
    else:
        xs = [positions[n][0] for n in names]
        ys = [positions[n][1] for n in names]
        ax.set_xlim(min(xs) - 2, max(xs) + 2)
        ax.set_ylim(min(ys) - 2, max(ys) + 2)

    ax.set_aspect("equal")
    plt.axis("off")

    # Farveforklaring (to rækker)
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

    # Titel
    dato = datetime.now().strftime("%d-%m-%Y")
    titel = f"Sociogram for {klasse_navn}" if klasse_navn else "Sociogram"
    plt.title(
        f"{titel}\nAlle peger på {num_choices} andre\nGenereret den {dato}",
        fontsize=14
    )

    # PNG
    png_buffer = BytesIO()
    fig.savefig(png_buffer, format="png", dpi=80, bbox_inches="tight")
    png_buffer.seek(0)
    st.image(png_buffer)

    # PDF
    pdf_buffer = BytesIO()
    fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight")
    pdf_buffer.seek(0)

    st.download_button(
        "Download sociogram som PDF",
        data=pdf_buffer,
        file_name="sociogram.pdf",
        mime="application/pdf",
    )
