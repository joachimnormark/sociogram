import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
import math
from io import BytesIO

st.title("Sociogram-generator")

st.write("Upload en CSV-fil med elevnavne og deres valg.")

uploaded_file = st.file_uploader("Vælg CSV-fil", type=["csv"])

if uploaded_file is not None:

    # === 1. Læs CSV med automatisk separator ===
def smart_read_csv(file):
    # Prøv semikolon
    try:
        return pd.read_csv(file, sep=";")
    except Exception:
        file.seek(0)

    # Prøv komma
    try:
        return pd.read_csv(file, sep=",")
    except Exception:
        file.seek(0)

    # Prøv tabulator
    try:
        return pd.read_csv(file, sep="\t")
    except Exception:
        file.seek(0)

    # Hvis alt fejler
    raise ValueError("Kunne ikke læse CSV-filen. Prøv at gemme den igen som CSV i Excel.")



    # === 2. Tjek om første række er kolonneoverskrifter ===
    first_cell = str(df.iloc[0, 0]).strip().lower()

    if first_cell in {"elev"}:
        # Første række ER kolonneoverskrifter
        df = pd.read_csv(uploaded_file, sep=None, engine="python")
        df.columns = df.columns.str.strip().str.lower()
    else:
        # Første række er data → lav egne kolonnenavne
        num_cols = df.shape[1]
        cols = ["elev"] + [str(i) for i in range(1, num_cols)]
        df.columns = cols
        df.columns = df.columns.str.lower()

    # === 3. Antal valg (kan være 2, 3 eller 4) ===
    all_columns = list(df.columns)
    choice_columns = [c for c in all_columns if c != "elev"]
    num_choices = len(choice_columns)

    if num_choices < 2 or num_choices > 4:
        st.error("Filen skal have 3, 4 eller 5 kolonner (elev + 2-4 valg).")
        st.stop()

    # === 4. Tjek for manglende valg ===
    missing = []
    for _, row in df.iterrows():
        elev = row["elev"]
        for c in choice_columns:
            if pd.isna(row[c]) or str(row[c]).strip() == "":
                missing.append(elev)
                break

    if missing:
        names = ", ".join(sorted(set(missing)))
        st.error(f"Følgende elever peger ikke på {num_choices} andre: {names}")
        st.stop()

    # === 5. Tjek for selv-reference ===
    self_ref = []
    for _, row in df.iterrows():
        elev = str(row["elev"]).strip().lower()
        for c in choice_columns:
            if elev == str(row[c]).strip().lower():
                self_ref.append(row["elev"])
                break

    if self_ref:
        names = ", ".join(sorted(set(self_ref)))
        st.error(f"Følgende elever peger på sig selv: {names}")
        st.stop()

    # === 6. Beregn kontakter ===
    all_names = pd.concat([df["elev"]] + [df[c] for c in choice_columns])
    contacts_count = all_names.value_counts().to_dict()

    # === 7. Layout i cirkel ===
    nodes = {}
    n = len(contacts_count)
    radius_circle = 5

    for i, elev in enumerate(contacts_count.keys()):
        angle = 2 * math.pi * i / n
        x = radius_circle * math.cos(angle)
        y = radius_circle * math.sin(angle)
        nodes[elev] = {"pos": (x, y), "contacts": contacts_count[elev]}

    # === 8. Edges ===
    edges = []
    for _, row in df.iterrows():
        elev = row["elev"]
        for c in choice_columns:
            edges.append((elev, row[c]))

    # Find gensidige relationer
    mutual_edges = set()
    for a, b in edges:
        if (b, a) in edges:
            mutual_edges.add((a, b))
            mutual_edges.add((b, a))

    # === 9. Tegn sociogram ===
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(-radius_circle - 2, radius_circle + 2)
    ax.set_ylim(-radius_circle - 2, radius_circle + 2)
    ax.set_aspect("equal")

    def get_color(n):
        if n < 3:
            return "red"
        elif n < 6:
            return "orange"
        else:
            return "green"

    # Cirkler
    for elev, data in nodes.items():
        x, y = data["pos"]
        r = 0.3 + data["contacts"] * 0.05
        circle = Circle((x, y), r, color=get_color(data["contacts"]), ec="black", zorder=2)
        ax.add_patch(circle)
        ax.text(x, y, elev, ha="center", va="center", fontsize=10, zorder=3)

    # Pile
    for start, end in edges:
        if start not in nodes or end not in nodes:
            continue

        x1, y1 = nodes[start]["pos"]
        x2, y2 = nodes[end]["pos"]
        r_start = 0.3 + nodes[start]["contacts"] * 0.05
        r_end = 0.3 + nodes[end]["contacts"] * 0.05

        dx, dy = x2 - x1, y2 - y1
        dist = math.sqrt(dx**2 + dy**2)

        if dist == 0:
            continue

        offset_start = r_start / dist
        offset_end = r_end / dist

        new_x1 = x1 + dx * offset_start
        new_y1 = y1 + dy * offset_start
        new_x2 = x2 - dx * offset_end
        new_y2 = y2 - dy * offset_end

        if (start, end) in mutual_edges:
            color = "green"
            lw = 3
        else:
            color = "black"
            lw = 1

        arrow = FancyArrowPatch(
            (new_x1, new_y1),
            (new_x2, new_y2),
            arrowstyle="->",
            mutation_scale=15,
            color=color,
            linewidth=lw,
            zorder=3,
        )
        ax.add_patch(arrow)

    # === 10. Titel ===
    plt.title(f"Sociogram – alle peger på {num_choices} andre")

    legend_elements = [
        Circle((0, 0), 0.3, color="red", label="Ingen peger på"),
        Circle((0, 0), 0.3, color="orange", label="Nogle peger på (1-3)"),
        Circle((0, 0), 0.3, color="green", label="Mange peger på (4+)"),
    ]
    ax.legend(handles=legend_elements, loc="upper right")
    plt.axis("off")

    # Vis i Streamlit
    st.pyplot(fig)

    # PDF-download
    pdf_buffer = BytesIO()
    fig.savefig(pdf_buffer, format="pdf")
    pdf_buffer.seek(0)

    st.download_button(
        label="Download sociogram som PDF",
        data=pdf_buffer,
        file_name="sociogram.pdf",
        mime="application/pdf",
    )
