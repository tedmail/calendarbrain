def make_invite_description(priority: str, notes: str, agenda_items):
    agenda = "".join([f"- {i}\n" for i in agenda_items])
    return f"Priority: {priority}\n\nNotas:\n{notes}\n\nPauta sugerida:\n{agenda}"
