"""Fixed facts about the Goethe B1 Hören exam and this project's generation policy.

The reasoning behind the traps and rules lives in plan/hoeren-exam-ontology.md.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = ROOT / "plan" / "hoeren-exam-ontology.md"
EXAMS = ROOT / "exams"

TF, MC, SPEAKER = "true_false", "multiple_choice", "speaker_matching"
TF_OPTIONS = ["richtig", "falsch"]
MC_OPTIONS = ["a", "b", "c"]

# Official structure (adult Modellsatz, Durchführungsbestimmungen 2025).
PARTS = {
    1: {
        "numbers": range(1, 11),
        "plays": 2,
        "instruction": "Sie hören nun fünf kurze Texte. Sie hören jeden Text zweimal. "
        "Zu jedem Text lösen Sie zwei Aufgaben. Wählen Sie bei jeder Aufgabe die richtige Lösung.",
    },
    2: {
        "numbers": range(11, 16),
        "plays": 1,
        "instruction": "Sie hören nun einen Text. Sie hören den Text einmal. "
        "Dazu lösen Sie fünf Aufgaben. Wählen Sie bei jeder Aufgabe die richtige Lösung a, b oder c.",
    },
    3: {
        "numbers": range(16, 23),
        "plays": 1,
        "instruction": "Sie hören nun ein Gespräch. Sie hören das Gespräch einmal. "
        "Dazu lösen Sie sieben Aufgaben. Wählen Sie: Sind die Aussagen richtig oder falsch?",
    },
    4: {
        "numbers": range(23, 31),
        "plays": 2,
        "instruction": "Sie hören nun eine Diskussion. Sie hören die Diskussion zweimal. "
        "Dazu lösen Sie acht Aufgaben. Ordnen Sie die Aussagen zu: Wer sagt was?",
    },
}

TRAPS = [
    "ACTOR_SWAP", "RECIPIENT_SWAP", "ROLE_SWAP", "PLAN_ACTUAL", "OLD_NEW",
    "FORECAST_ACTUAL", "WANT_DO", "AVAILABLE_CHOSEN", "MENTIONED_TRUE", "CAUSE_SWAP",
    "PLACE_SWAP", "TIME_SWAP", "QUANTITY_SCOPE", "MODALITY", "NEGATION", "CONDITION",
    "TEMPORAL_SCOPE", "PART_WHOLE", "REQUEST_ACTION", "REQUEST_RESULT",
    "SOURCE_ATTRIBUTION", "QUOTE_ATTRIBUTION", "STANCE_QUALIFIER", "KEYWORD_OVERLAP",
    "PARAPHRASE", "DISTRACTOR_DENSITY",
]
SLOTS = [
    "WHO", "WHAT", "WHEN", "WHERE", "WHY", "HOW_MUCH", "POLARITY", "MODALITY",
    "STATUS", "SCOPE", "CONDITION", "SOURCE",
]

# Which traps suit which part; the blueprint draws from these.
PART_TRAPS = {
    "1_global": ["PLAN_ACTUAL", "OLD_NEW", "NEGATION", "PARAPHRASE", "MENTIONED_TRUE", "CONDITION"],
    "1_detail": ["MENTIONED_TRUE", "CAUSE_SWAP", "PLACE_SWAP", "TIME_SWAP", "REQUEST_ACTION",
                 "DISTRACTOR_DENSITY", "QUANTITY_SCOPE", "OLD_NEW"],
    2: ["PLACE_SWAP", "TIME_SWAP", "MODALITY", "QUANTITY_SCOPE", "CONDITION", "TEMPORAL_SCOPE",
        "PART_WHOLE", "DISTRACTOR_DENSITY", "MENTIONED_TRUE"],
    3: ["ACTOR_SWAP", "RECIPIENT_SWAP", "ROLE_SWAP", "PLAN_ACTUAL", "FORECAST_ACTUAL", "WANT_DO",
        "AVAILABLE_CHOSEN", "REQUEST_RESULT", "TEMPORAL_SCOPE", "NEGATION", "CAUSE_SWAP"],
    4: ["SOURCE_ATTRIBUTION", "QUOTE_ATTRIBUTION", "STANCE_QUALIFIER", "KEYWORD_OVERLAP", "PARAPHRASE"],
}

TEIL1_TEXT_TYPES = [
    "voicemail from a doctor's practice",
    "voicemail from a landlord or property management",
    "voicemail from an employer or colleague",
    "voicemail from a language school or course provider",
    "voicemail from a shop, workshop or delivery service",
    "private voicemail from a friend or relative",
    "station or platform announcement",
    "airport or bus-station announcement",
    "radio traffic report",
    "radio weather forecast",
    "radio notice about a local event or competition",
    "announcement in a department store or supermarket",
    "announcement in a public building (library, swimming pool, town hall)",
    "tourist information or city-tour notice",
]
TEIL2_SETTINGS = [
    "first-day orientation talk for new employees at a company",
    "introduction to a language-school summer course",
    "guided walk through an old town by a city guide",
    "welcome talk at a youth hostel or holiday apartment complex",
    "introduction to a cooking or craft course weekend",
    "guided visit of a factory or brewery",
    "welcome talk on a river boat trip",
    "information talk at a newly opened public library",
    "welcome talk for volunteers at a city festival",
    "introduction to a zoo or botanical garden visit",
    "information evening for a new sports or fitness club",
    "welcome talk for a group at a farm holiday",
]
TEIL3_SCENARIOS = [
    "two colleagues on the bus talk about one of them moving to a new flat",
    "two friends in a café talk about a recent city trip",
    "two neighbours talk about a family celebration one of them attended",
    "two acquaintances talk about a first week in a new job",
    "two friends talk about a concert or festival visit",
    "two former classmates meet and talk about a camping holiday",
    "two friends talk about a failed and then successful attempt to buy a used car",
    "two colleagues talk about a weekend helping relatives renovate",
    "two friends talk about a cooking course that went differently than planned",
    "two neighbours talk about a trip to visit family abroad",
]
TEIL4_TOPICS = [
    "Should shops be open on Sundays?",
    "Are smartphones harmful in secondary schools?",
    "Should cities ban cars from the centre?",
    "Is working part-time a good model for everyone?",
    "Should young people do a voluntary social year after school?",
    "Is online shopping bad for city centres?",
    "Should pets be allowed in rented flats?",
    "Do we still need cash?",
    "Is a four-day working week realistic?",
    "Should homework be abolished?",
    "Are video games a good hobby for adults?",
    "Should adult children live with their parents to save money?",
]

# Approved cast: Petra solo female, Markus solo male,
# Anna female only in dialogues together with Markus. Keys index scripts/tts.py VOICES.
SOLO = {"f": "petra", "m": "markus"}
DIALOGUE = {"f": "anna", "m": "markus"}

# Soft length targets in words (warnings only).
WORDS = {
    "unit1": (55, 120),
    2: (420, 650),
    3: (480, 750),
    4: (620, 950),
    "turn_max": 90,
    "tf": (4, 12),
    "speaker_statement": (5, 14),
}

# Telegram Bot API limits.
TG_POLL_QUESTION = 300
TG_POLL_OPTION = 100
TG_POLL_EXPLANATION = 200
TG_MESSAGE = 4096
