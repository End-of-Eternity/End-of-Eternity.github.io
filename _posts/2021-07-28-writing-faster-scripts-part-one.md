---
layout: post
title: "Writing Faster Scripts - Part 1"
category: "Vapoursynth Scripting"
date: 2021-07-28 16:22:00 +0100
---



A couple of weeks ago, someone in the [IEW Discord server](https://discord.gg/qxTxVJGtst) mentioned that one of their scripts was running slow, and asked if I could take a look at it. Within their script was something like this:

_The original (slow) code_
```python
insertion_frame_indexes = [...]  # A couple hundred frame indexes to duplicate
for i in insertion_frame_indexes:
    clip = clip[:i] + clip[i + 1] + clip[i:]
```

For those with less Python/Vapoursynth experience, all this is doing is duplicating the frames at the indexes specified in `insertion_frame_indexes`. Seems fairly simple right? If `clip` was just a list of integers, this would take a few milliseconds to run on any half decent hardware, but we have to remember that this is a Vapoursynth clip, and they work a little different.

Running this functon with a blank 1080p clip on my machine, and then outputting `clip` will take around 1s to output the first frame, and then runs at a pretty miserable 200fps. Given that a blank clip generates at around a maximum of 2000fps for me, that's not ideal. I managed to fix this with some more optimised code that ran at a solid 1600fps, which you can see below, but the real question a few people had was 'Why is just splicing clips together so slow?'

_My improved code_
```python
# insertion_frame_indexes same as above
frame_indexes = list(range(clip.num_frames))
for i in insertion_frame_indexes:
    frame_indexes = frame_indexes[:i] + frame_indexes[i + 1] + frame_indexes[i:]
placeholder = core.std.BlankClip(clip, length=len(frame_indexes))

def _insert_frames_func(n: int, f):
    return clip.get_frame(frame_indexes(n))

clip = core.std.ModifyFrame(placeholder, placeholder, _insert_frames_func)
```

_[Taken from the lvsfunc channel in IEW](https://discord.com/channels/856381934052704266/856383388889120778/864481652108951553)_
> louis: how the f**k is modifyframe faster than splice

Lets see if we answer louis' question can figure out why this seemingly fast code runs so slowly, and then look at why my implementation was so much faster.

## Analysis of the original: Why was it so slow?

Whenever I run into a problem with code, be that it's giving unexpected outputs, it's running unreasonably slow, or it is just plain not working, often a good place I'll to look is at how the functions I'm using work. Let's have a look at what our original code does underneath the pretty syntax.

Our main offending line is `clip = clip[:i] + clip[i + 1] + clip[i:]`. In python, using `[]` after a variable calls it's `__getitem__` method, and then the `+` operator calls the `__add__` method. If we take a look at [how these are implemented](https://github.com/vapoursynth/vapoursynth/blob/master/src/cython/vapoursynth.pyx#L1570) for the `VideoNode` class, we can see that the line roughly translates to the following:

```python
# I have split this up onto multiple lines for readability.
first = core.std.Trim(clip, last=i - 1)
insert = core.std.Trim(clip, first=i + 1, length=1)
last = core.std.Trim(clip, first=i)
clip = core.std.Splice([core.std.Splice([first, insert]), last])
```

Already, we can see some simple problems with this section of code. For example, `std.Splice` can accept a list of clips, so the final line could become `core.std.Splice([first, insert, last])` to be a little less bloated, however this hasn't solved the root of the problem. The real issue here is the `for` loop. Becausse we execute this section of code for every insertion frame in the list, we're essentially chaining hundreds, or even thousands of `std.Trim` and `std.Splice` calls.

Now, you might wonder why this is an issue: trimming and splicing clips can't be all that intensive a task for your RGB gaming rig, so why does it go so slow? The problem is that Vapoursynth doesn't just do the splicing at the very beginning, and then run the rest of your filters on the rest of the frames - it instead works quite differently.

## How does Vapoursynth *Actually* work?

Each filter in Vapoursynth must implement a few functions, one of which being an initialiser which reads your parameters, and sets the video info for the clip that is output, and another to get a frame at some position. When you run a Vapoursynth function, all you're actually doing is calling the initialiser: no processing of the video is (usually[^1]) done.

This is usually ideal: Vapoursynth is a frame server, we only want the frames to be processed and given to us when we want them, otherwise we'd be waiting hours before being able to get the first few frames of video. However, in this case it does shoot us in the foot.

For the `Trim` and `Splice` functions, we can take a look at the [source code](https://github.com/vapoursynth/vapoursynth/blob/master/src/core/reorderfilters.c#L496) to see what's happening. Both filters are obviously very simple, but they both have to get, and then return the correct frame from within the `GetFrame` function. This has only a little overhead, but when you've chained hundreds of functions together, this does start to add up.

The tl;dr here is that the original couple lines of code expands to a very large number of functions, each of which depending on the last in order to get the next frame, creating a massive dependancy chain which hogs both CPU time and memory.

[^1]: This has been vastly simplified - some filters will do certain things that only need doing once during this stage.

## Making a faster function

We already know what the output clip should look like - so there's no need to call lots of functions and force Vapoursynth to create a massive filterchain that's just going to hog your CPU time. Instead, we can just be a little more clever in how we stitch our clip together, to make it happen in just one function instead of one thousand.

Let's go through my original function line by line to see how it runs much faster.

```python
# Firstly, we create a list of frames in the original clip.
frame_indexes = list(range(clip.num_frames))

# Next we perform all the logic in duplicating the frames.
# This is actually just copy pasted from the original code,
# but since this time we're using python lists, it's
# significantly faster, and doesn't create a long dependancy
# chain of filters that Vapoursynth will have to deal with
# later on. We can then use this as a mapping between the
# index of a frame in the new clip, and the old clip
for i in insertion_frame_indexes:
    frame_indexes = frame_indexes[:i] + frame_indexes[i + 1] + frame_indexes[i:]

# We have to create a placeholder clip with the length, and
# format of the original, so that we request the right
# amount of frames from our later `ModifyFrame` function,
# and so later Vapoursynth filters know how to work with our
# clip.
placeholder = core.std.BlankClip(clip, length=len(frame_indexes))

# This is the function we'll pass to `ModifyFrame` that will
# actually request the correct frame at each index. I'm using
# `ModifyFrame` here only because it's a little faster than
# `FrameEval`, but both are equally usable.
# `f` here is unused, however `ModifyFrame` will still pass
# it anyway, so it must be left in order not to error out.
def _insert_frames_func(n: int, f):
    return clip.get_frame(frame_indexes(n))

# Finally, we actually run our insertion function over the
# placeholder clip, and get back exactly the same thing as
# before, only this time in a single function, and multiple
# times faster. Neat.
clip = core.std.ModifyFrame(placeholder, placeholder, _insert_frames_func)
```

## What We've Learnt

Overall, the final function is actually really rather simple - but fast code doesn't need to be complex. What's important here, is recognising how Vapoursynth does the processing internally, and working with it's strengths. This doesn't really follow the [Zen of Python](https://www.python.org/dev/peps/pep-0020/)'s rule of _"There should be one-- and preferably only one --obvious way to do it,"_ but in my opinion this is still a readable, and possibly more explicit way to do the original function.

If you only took one thing away from this little talk of mine, then it should be to look closer at the Vapoursynth source. Don't just assume that the obvious way is the fastest - figure out why it's not, and then come up with something better. Python's pretty powerful - and with `FrameEval`/`ModifyFrame` you can do some wacky stuff without needing to write a full plugin.

For my next post in this topic, I'm planning on talking about using `numpy` for speed boosts, and prototyping new functions in a nice and simple Python script. If you've got any feedback at all, please send it my way on Discord. I can be found hanging around on the [IEW Discord server](https://discord.gg/qxTxVJGtst), or alternatively you can just leave an issue on the [Github repo](https://github.com/End-of-Eternity/End-of-Eternity.github.io) where this project is hosted from
