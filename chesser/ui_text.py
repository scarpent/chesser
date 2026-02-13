class Tooltips(dict):
    def __missing__(self, key):
        return f"[missing tooltip: {key}]"


TOOLTIPS = Tooltips(
    {
        # Global nav
        "home": "Home",
        "review_next_due": "Review Next Due",
        "edit": "Edit",
        "view": "View",
        "white_openings": "White Openings",
        "black_openings": "Black Openings",
        "import_export": "Import / Export",
        "stats": "Stats",
        # Review / practice
        "practice": "Practice without recording history or advancing level",
        "learn": "Start regular review with spaced repetition",
        "restart": "Restart",
        "show_move": "Show Move",
        "variation_info": "Variation Info",
        "review_next": "Next",
        "review_finish": "Finish",
        "random_extra_study": "Random Extra Study",
        "lichess_puzzles": "Lichess Puzzles",
        # Admin
        "admin_open": "Open in Django admin",
        "django_admin": "Django Admin",
        # Navigation
        "mainline_back": "Previous mainline move",
        "mainline_forward": "Next mainline move",
        "go_to_top": "Go to top",
        # Chapter / misc
        "chapter_jump": "Go to chapter and highlight this line",
        "copy_fen": "Copy FEN for currently displayed position",
        "lichess_analysis": "Lichess analysis board",
        "alts_help": "Show alternative move arrows (yellow = pass, red = fail)",
        "save_all": "Save All",
        "help": "Open Help for this page in the project README",
    }
)
