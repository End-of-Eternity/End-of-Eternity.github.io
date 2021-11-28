---
layout: post
title: "Writing Faster Scripts - Part 2"
category: "Vapoursynth Scripting"
date: 2021-11-28 00:25:00 +0000
---

It has been exactly 4 months since the first installation of this little series of mine, however I've finally gotten the motivation to actually write something again. It's not the numpy related post as I promised in part 1, however I can at least confirm that that is coming (see [the vsnumpy overhaul in EoEfunc](https://gitlab.com/arjraj/EoEfunc/-/blob/good_array_eval/EoEfunc/vsnumpy.py)). In the meantime though, I wanted to talk more about using `FrameEval`s.

Firstly, I need to make a correction regarding the differences between `FrameEval` and `ModifyFrame`. I had originally said,

> "I'm using `ModifyFrame` here only because it's a little faster than `FrameEval`, but both are equally usable." _- Me, [Writing Faster Scripts - Part 1](/vapoursynth%20scripting/2021/07/28/writing-faster-scripts-part-one.html)_

However, there is a fairly significant difference between the two. `FrameEval` expects a `VideoNode` to be returned, where `ModifyFrame` expects a `VideoFrame`. This means that if you don't know the exact frame index to be returned ahead of time, you must use `clip.get_frame(index)` for `ModifyFrame`. I had originally thought this to be a non issue, however after reports of hanging by multiple people, this was obviously incorrect. Myrsloik (the Vapoursynth dev) [said they think that python's GIL causes this issue](https://discord.com/channels/856381934052704266/856383302097043497/896037998880247851) _([IEW Discord](https://discord.gg/qxTxVJGtst))_, but regardless of what it's caused by, it *can* cause a problem, and therefore we should use `FrameEval` instead, and accept that it's *ever so slightly* slower. Having said that, with the new API4 changes, `FrameEval` may have gained the performance difference back anyway. Oh, and this doesn't occur with `FrameEval` because it requests the frame internally instead, bypassing the python threading issues.

Anyway, enough about what mistakes I made, let's talk about mistakes other people made instead, and how they can be avoided in future.

# Writing a ~~Good~~ _Fast_ `FrameEval` Function

The secret to a fast `FrameEval` is to do as little as possible within the function. What I mean by this, is taking as much of the logic as possible outside. Often this means you'll end up with a single `if` statement within the `eval` function, which just determines one of two clips to be returned. The more logic you put into the `FrameEval`, the more that has to be done every frame, and remember, Python is slow.

Here's an example, helpfully "provided" by [LightArrowsEXE](https://discord.com/channels/856381934052704266/856383302097043497/914282516444221463) _([IEW Discord](https://discord.gg/qxTxVJGtst))_

```python
# All further examples will assume these imports
import vapoursynth as vs
from functools import partial
from vsutil import scale_value, get_depth
from lvsfunc.misc import get_prop

core = vs.core


def auto_lbox(clip: vs.VideoNode, flt: vs.VideoNode, flt_lbox: vs.VideoNode,
              crop_top: int = 130, crop_bottom: int = 130) -> vs.VideoNode:
    """
    Automatically determining what scenes have letterboxing
    and applying the correct edgefixing to it
    """

    def _letterboxed(n: int, f: vs.VideoFrame,
                     clip: vs.VideoNode, flt: vs.VideoNode, flt_lbox: vs.VideoNode
                     ) -> vs.VideoNode:
        crop = (
            core.std.CropRel(clip, top=crop_top, bottom=crop_bottom)
            .std.AddBorders(top=crop_top, bottom=crop_bottom, color=[luma_val, chr_val, chr_val])
        )

        clip_prop = round(get_prop(clip.std.PlaneStats().get_frame(n), "PlaneStatsAverage", float), 4)
        crop_prop = round(get_prop(crop.std.PlaneStats().get_frame(n), "PlaneStatsAverage", float), 4)

        if crop_prop == clip_prop:
            return flt_lbox.std.SetFrameProp("Letterbox", intval=1)
        return flt.std.SetFrameProp("Letterbox", intval=0)

    luma_val = scale_value(16, 8, get_depth(clip))
    chr_val = scale_value(128, 8, get_depth(clip))

    return core.std.FrameEval(clip, partial(_letterboxed, clip=clip, flt=flt, flt_lbox=flt_lbox), clip)
```

Since this is LightCode™, there's a helpful docstring to tell us that all this does is select a clip based on whether or not it has letterboxing. It works (I think), though it could definately do with some improvements. Starting with the first line of the function, we can see our first problem.
```python
crop = (
    core.std.CropRel(clip, top=crop_top, bottom=crop_bottom)
    .std.AddBorders(top=crop_top, bottom=crop_bottom, color=[luma_val, chr_val, chr_val])
)
```

That looks like logic to me! This could definately be moved outside of our `eval` function, since nothing here depends on anything we calculated inside of the `FrameEval`.

The next lines are very problematic, as they use the cursed `get_frame` method, which as we discussed earlier, can cause Python to hiss at you (actually it does nothing and hangs, which is probably worse).
```python
clip_prop = round(get_prop(clip.std.PlaneStats().get_frame(n), "PlaneStatsAverage", float), 4)
crop_prop = round(get_prop(crop.std.PlaneStats().get_frame(n), "PlaneStatsAverage", float), 4)
```

There's luckily an easy fix to this too, as all Light is doing with these frames is reading a prop, which is what `FrameEval` is built for. Any clips passed to the `prop_src` (third) argument of `FrameEval` have their frames passed to the `eval` function in the `f` parameter, meaning we can add these two clips to the `prop_src`. Light actually got halfway there, putting `clip` into `prop_src`, though he forgot to actually use it in the `eval` func.

Finally, this gets us to the only required bit of logic in this function, the bit that chooses which clip to return:
```python
if crop_prop == clip_prop:
    return flt_lbox.std.SetFrameProp("Letterbox", intval=1)
return flt.std.SetFrameProp("Letterbox", intval=0)
```

The only change needed here is that we can set the props for `flt` and `flt_lbox` outside of the `FrameEval` instead. This might seem like something that won't affect performance at all, since setting a frame prop can't take all that long, however the issue is that this filter will be reinitilised *every* time the `eval` func is called. Since Vapoursynth evaluates frames [lazily](https://en.wikipedia.org/wiki/Lazy_evaluation) (as they are required), there's no harm in setting the frame props for both clips, before the `eval`, since the filter logic will only be called when the frames are requested. This goes for all filters too, meaning as long as you don't need to change a filter parameter based on an individual frame, it will always be faster to take the logic out of the `FrameEval`.

After all of our changes, our modified function looks like so:
```python
def auto_lbox(...) -> vs.VideoNode:
    """
    Automatically determining what scenes have letterboxing
    and applying the correct edgefixing to it
    """

    def _letterboxed(
        n: int, f: list[vs.VideoFrame], clip: vs.VideoNode, flt: vs.VideoNode, flt_lbox: vs.VideoNode
    ) -> vs.VideoNode:

        clip_prop = round(get_prop(f[0], "PlaneStatsAverage", float), 4)
        crop_prop = round(get_prop(f[1], "PlaneStatsAverage", float), 4)

        if crop_prop == clip_prop:
            return flt_lbox
        return flt

    flt_lbox = core.std.SetFrameProp(flt_lbox, "Letterbox", intval=1)
    flt = core.std.SetFrameProp(flt_lbox, "Letterbox", intval=0)

    luma_val = scale_value(16, 8, get_depth(clip))
    chr_val = scale_value(128, 8, get_depth(clip))
    crop = (
        core.std.CropRel(clip, top=crop_top, bottom=crop_bottom)
        .std.AddBorders(top=crop_top, bottom=crop_bottom, color=[luma_val, chr_val, chr_val])
        .std.PlaneStats()
    )

    return core.std.FrameEval(
        clip,
        eval = partial(_letterboxed, clip=clip, flt=flt, flt_lbox=flt_lbox),
        prop_src = [clip.std.PlaneStats(), crop],
    )
```

Look how small our `eval` function is now! Pretty much everything was moved outside, leaving only the rounding of the frame prop, and the comparison to determine which clip to return. If I was really anal, I could rewrite `PlaneStats` to automatically round to the 4th decimal place, though I'm pretty sure Python can do that fast enough to not be an issue.

# A Conclusion

The best thing about this is that there is _no_ difference in output, and it didn't require any clever maths optimisations or anything to be improved. All that really needs to be done to improve the majority of `eval` functions, is just a reordering of the logic, and some thought put into what actually _needs_ to be done within it. I hope that this encourages more people put off in the past by the apparent "abysmal performance" of `FrameEval` to try writing their own functions with a little more care. Anyone who's unsure about anything can always feel free to contact me (End of Eternity#6292) on Discord, best done through the [IEW Discord Server](https://discord.gg/qxTxVJGtst).

Cheers, and see you "soon" for some Vapoursynth + numpy magic.