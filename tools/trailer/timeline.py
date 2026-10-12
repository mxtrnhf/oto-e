"""When things happen in the trailer, in seconds. The picture and the sound are both built from this, so they stay in step."""
FPS = 30
W, H = 1920, 1080
TOTAL = 110.0

TITLE = (0.0, 7.0)
BYTES = (7.0, 17.0)           # the clean picture, then "bytes can be sound"
EFFECT_START, EFFECT_LEN, REVEAL_LEN = 17.0, 6.0, 2.6
EFFECTS = ["Echo", "Bass and Treble", "Tape Recording (record → age → playback)", "Bitcrusher", "Block Displacement", "Spectral Blur", "Noise Convolution (smear)"]
SHORT = ["Echo", "Bass and Treble", "Tape Recording", "Bitcrusher", "Block Displacement", "Spectral Blur", "Noise Convolution"]
OVERRIDES = {"Bass and Treble": {"bass": -12, "treble": 12}}  # settings other than the defaults, where the default is not the most telling
UNDO = (59.0, 65.0)           # back to the original picture: "nothing is lost"
UI = (65.0, 79.0)
RECIPE = (79.0, 103.0)        # a recipe, then the layout of a project file: long holds so it can be read
END = (103.0, 110.0)

effect_times = [EFFECT_START + i * EFFECT_LEN for i in range(len(EFFECTS))]
# moments with a glitch burst (time, strength 0..1): only the title and the end card; the picture changes are calm
glitches = [(1.2, .35), (3.6, .5), (5.9, .35), (END[0] + .5, .5)]
