"""The dāra system — one construction for the logo and the four states.
Source (primary): Ibn al-Salāḥ, Muqaddima, type 25, rule 7 — scholars put a dāra (circle) between every two
hadiths; al-Khaṭīb preferred them left empty (ghufl) and, once a text was collated against its source,
a dot was placed inside. → empty dāra = not yet matched; dotted dāra = collated against the source.
Grid: 24 units. Ring r=8 (stroke 3 → survives 16px). Nuqta = rhombus, diagonal 8 (Ibn Muqla's unit, pen-pressed)."""
def dara(state="found", size=24, color="currentColor", sw=3.0):
    c=12; r=8
    ring=f'<circle cx="12" cy="12" r="{r}" fill="none" stroke="{color}" stroke-width="{sw}"/>'
    rh=lambda d,fill: f'<path d="M12 {12-d} L{12+d} 12 L12 {12+d} L{12-d} 12Z" fill="{fill}" stroke="{color}" stroke-width="{1.6 if fill=="none" else 0}" stroke-linejoin="round"/>'
    if state=="found":      inner=rh(4,color)                                   # collated: the dot
    elif state=="partial":  inner=rh(3.6,"none")                                # collated, words differ: hollow dot
    elif state=="review":   inner=f'<rect x="7.5" y="10.5" width="9" height="3" rx="1.5" fill="{color}"/>'  # bar across: not yet settled — look again
    else:                   inner=""                                            # ghufl: empty, not matched in our sources
    return f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true" class="dara">{ring}{inner}</svg>'
def logo(size=40, ink="#12183F", dot="#5B48E8", bg=None):
    b=f'<rect width="24" height="24" rx="6" fill="{bg}"/>' if bg else ""
    sw=2.6 if bg else 3
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true">{b}'
            f'<circle cx="12" cy="12" r="{7.6 if bg else 8.5}" fill="none" stroke="{ink}" stroke-width="{sw}"/>'
            f'<path d="M12 7.4 L16.6 12 L12 16.6 L7.4 12Z" fill="{dot}"/></svg>')
