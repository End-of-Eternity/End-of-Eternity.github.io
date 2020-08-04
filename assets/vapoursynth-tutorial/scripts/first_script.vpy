import vapoursynth as vs
core = vs.get_core()

my_clip = core.std.BlankClip(width=1920, height=1080, length=1000, fpsnum=24, color=[255, 0, 0])
my_clip.set_output()