APP_STYLES = """
<style>
body {
    background: #0b1220;
}

/* HEADER */
.main-title {
    font-size: 40px;
    font-weight: 800;
    text-align: center;
    background: linear-gradient(90deg,#60a5fa,#a78bfa,#34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 5px;
}

.subtitle {
    text-align:center;
    color: #94a3b8;
    margin-bottom: 30px;
}

/* CARD */
.activity-card {
    padding: 18px;
    border-radius: 18px;
    background: linear-gradient(135deg, #0f172a, #111827);
    color: white;
    margin-bottom: 12px;
    box-shadow: 0px 8px 30px rgba(0,0,0,0.4);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.activity-card:hover {
    transform: translateY(-6px);
    box-shadow: 0px 12px 40px rgba(59,130,246,0.25);
}

/* SCORE */
.score {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 999px;
    font-weight: bold;
    font-size: 12px;
    color: white;
    background: linear-gradient(90deg,#22c55e,#3b82f6);
}

/* TYPE */
.type {
    font-size: 12px;
    opacity: 0.7;
}

/* INSIGHT */
.insight {
    padding: 24px;
    border-radius: 22px;
    background: radial-gradient(circle at top left, #111827, #0b1220);
    color: white;
     box-shadow: 0px 0px 40px rgba(59,130,246,0.15);
    line-height: 1.7;
}

.insight-title {
    font-size: 18px;
    font-weight: 700;
    background: linear-gradient(90deg,#60a5fa,#a78bfa,#34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* SIDEBAR */
.sidebar-title {
    font-size: 22px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 12px;
    background: linear-gradient(90deg,#60a5fa,#a78bfa,#34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.section-title {
    font-size: 12px;
    opacity: 0.7;
    margin: 10px 0 6px 2px;
     letter-spacing: 0.5px;
}
hr {
    border: none;
    height: 1px;
    background: rgba(255,255,255,0.06);
    margin: 12px 0;
}

/* BUTTON CONTAINER */
div.stButton {
    padding-left: 6px;
    padding-right: 6px;
    margin-top: 18px;
}
/* MAIN BUTTON */
div.stButton > button {
    width: 100%;
    min-width: 260px;   
    max-width: 100%;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 0.4px;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.08);
    color: white;
    background: linear-gradient(90deg,#60a5fa,#a78bfa,#34d399);
    box-shadow:
        0px 8px 25px rgba(59,130,246,0.35),
        0px 0px 0px rgba(96,165,250,0);

    transition: all 0.3s ease;
}
/* CENTER BUTTON */
div.stButton {
    display: flex;
    justify-content: center;
    margin-top: 18px;
}
/* HOVER EFFECT */
div.stButton > button:hover {
    transform: translateY(-3px);
    box-shadow:
        0px 14px 35px rgba(59,130,246,0.55),
        0px 0px 18px rgba(96,165,250,0.55);
    border: 1px solid rgba(255,255,255,0.18);
}
/* CLICK EFFECT */
div.stButton > button:active {
    transform: scale(0.98);
}

.empty-state {
        padding: 40px;
        border-radius: 20px;
        text-align: center;
        background: radial-gradient(circle at top left, #0f172a, #020617);
        color: white;
        box-shadow: 0px 0px 40px rgba(59,130,246,0.15);
        animation: floaty 3s ease-in-out infinite;
    }

    @keyframes floaty {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-6px); }
        100% { transform: translateY(0px); }
    }

    .emoji {
        font-size: 40px;
        margin-bottom: 10px;
        animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.15); }
        100% { transform: scale(1); }
    }

    .title {
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 8px;
    }

    .subtitle {
        font-size: 14px;
        opacity: 0.7;
    }
    .loading-box {
    padding: 18px;
    border-radius: 16px;
    background: linear-gradient(135deg, #0f172a, #111827);
    color: white;
    text-align: center;
    font-size: 16px;
    font-weight: 600;
    box-shadow: 0px 0px 25px rgba(59,130,246,0.15);
    margin: 10px 0;
    animation: pulseBox 1.5s infinite;
}

@keyframes pulseBox {
    0% { transform: scale(1); opacity: 0.7; }
    50% { transform: scale(1.02); opacity: 1; }
    100% { transform: scale(1); opacity: 0.7; }
}

.loading-dots::after {
    content: '...';
    animation: dots 1.2s infinite;
}

@keyframes dots {
    0% { content: ''; }
    33% { content: '.'; }
    66% { content: '..'; }
    100% { content: '...'; }
}
</style>
"""