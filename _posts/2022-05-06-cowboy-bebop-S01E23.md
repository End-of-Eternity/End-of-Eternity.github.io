---
layout: post
title: "Cowboy Bebop S01E23"
category: "My Vapoursynth Scripts"
date: 2022-05-06 17:30:00 +0100
---

_I should mention that this post is written from the perspective of someone who wants a small file,
and still good quality, not perfect quality with zero filesize constraints. Therefore, much of what
I do here would not be ideal for a bloated release._

I knew that Cowboy Bebop was going to be a large encode from the beginning, so seeing output files
ranging from 250-500MiB or even 700MiB wasn't terribly surprising, but when episode 23 completed and
I saw a size of 1.34GiB, I was a little worried. That's about 4-5 times the average Judas bitrate.
There's nothing inherantly wrong with a big file - I'm fine with episodes coming out at 450MiB
instead of 250MiB because crf is a _quality_ based metric, and so if the file comes out large, then
it's because x265 needed a few more bits to get a similar quality level. But, if a file comes out
*that big*, something's obviously wrong.

A quick glance at the source answered all questions I had immediately:

![Frame 5073](/assets/cowboy-bebop-s01e23/Bebop_23_5073.png)

Let's list the issues shall we?

- Strong dynamic grain ✓
- Weird horizontal lines that break motion estimation ✓
- Frames of pure static noise ✓
- Psychedelic effects with bright colours and quickly changing visuals ✓

x265 does _not_ like any of this. At all. So, what can we do to get better efficiency?

## The Dumb Method

Well, step 1 is just to try to make x265 compress more, after all, if the file is too big, the
simple solution is to ask x265 nicely to "make it smaller." I'd already used some fairly strong
settings on bebop, so I just tried increasing the crf by 1 (18-19). This, rather expectedly, didn't
do a whole lot, only reducing the file size from about 1.34GiB to 1.3GiB. Going further would likely
not have helped much either, only significantly reducing quality in non-fucked scenes (see
[Tenrai-Sensei's 912MiB CRF23 encode](https://pastebin.com/raw/v55MYYwD))

The real issue here is with the source, x265 is pretty good, but it's not magic, and it won't be
able to compress a video with all the issues listed above very well at all. I could always force the
bitrate to stay within a certain limit (say 9000kbps), but this will just cause the encoder to
destroy many frames that it can't figure out how to get below this bitrate constraint.

## Fixing the Source

So, we know what the issues are, how can we fix them? 3/4 issues aren't really "fixable" as they are
just a part of the show: I can't just cut out the scenes with this effect. However, we can at least
try to denoise it. The usual suspects (BM3D, knlm, ect.) aren't much use here: they aren't built to
deal with this sort of noise, and whilst at ultra high strengths they _can_ work, they aren't great.

### CMDegrain

Generally, if you're trying to get rid of dynamic grain, then the best bet is a temporal denoiser,
like `CMDegrain`. `CMDegrain` works best with high frequency noise (small dots), but at a high
enough strength it will basically get rid of any noise. The only problem is, the higher the strength,
the more motion blur it will cause.

Here's what I ended up coming up with:

```python
tv_cmde = eoe.dn.CMDE(
    src,
    tr=3,
    thSAD=500,
    thSADc=250,
    refine=5,
    prefilter=core.std.BoxBlur(src, 0, 6, 2, 1, 1),
    freq_merge=False,
    contrasharp=False,
)
```

Parameter Explanation:

- tr=3: Temporal radius. CMDE will consider up to 3 frames into the past and the future for motion
    and denoising.
- thSAD=500: Denoising strength (luma)
- thSADc=250: Denoising strength (chroma).
- refine=5: Number of times to recalculate motion vectors. Since getting accurate motion vectors
            from this video is extremely difficult, due to the horizontal lines, I recalulate
            vectors as many times as is possible with integer mvtools using different block sizes.
            This results in much better accuracy, with very little extra processing time.
- prefilter: Clip to calculate motion vectors from. I'm using a somewhat strong horizontal blur to
             try to get rid of a lot of the grain, without touching the vertical lines. I would
             generally use dfttest for this, but I was running out of cpu time.
- freq_merge=False: Don't use the internal freq merge implementation (because I'm using custom
                    parameters later on, and it's also slower)
- contrasharp=False: Don't contrasharpen. Actually redundant here (since False is the default), but
                     I was experimenting with it earlier. Unfortunately, it doesn't work well at all
                     due to the size and magnitude of the grain.

CMDegrain's motion blur at a thSAD of 500, and subpar motion vectors due to the horizontal bar
effect, is pretty bad. My usual method to fix this is to do a `freq_merge`: simply a way to merge
two clips together using their frequencies as weighting, instead of simple averaging. This allows us
to extract the low frequencies (lineart) from the source, and merge them with the high frequencies
(noise) of the denoised clip. This effectively allows us to use as strong as a denoise as is
necessary, without causing huge motion blur.

Unfortunately, the noise in this episode is fairly low frequency, and therefore is difficult to get
rid of without also causing some level of motion blur. My `freq_merge` settings try to strike a
balence between motion blur and denoising:

```python
tv_cmde = merge_frequency(
    src,
    tv_cmde,
    slocation=None,
    sigma=1024,
    ssx=[0.0, 0, 0.03, 0, 0.06, 16, 0.15, 56, 0.2, 1024, 1.0, 1024],
    smode=1,
    sbsize=8,
    sosize=6,
)
```


Parameter Explanation:

- src, tv_cmde: Sources to take low and high frequencies from.
- slocation=None: In order to extract frequencies from the x and y axis with different strengths, I
                  have to disable the internal slocation parameter.
- sigma=1024: Ultra high `DFTTest` strength, used across the y axis. This means that all frequencies
              are extracted from the denoised clip, and merged into the source clip, in the vertical
              direction. Since frequencies are transposed against lines in the time dimension, this
              means that all horizontal lines are copied from the denoised clip as is: i.e. the
              horizontal bar effect.
- ssx=[...]: Frequency extraction strengths from 0 (lowest frequency) to 1 (highest frequency).
             Since the noise in this episode is very large, I had to write a very precise custom
             slocation to try to avoid motion blur without leaving all the noise in.
- smode=1, sbsize=8, sosize=6: `DFTTest` processing parameters. Specified here as they give better
                               performance than the `freq_merge` defaults without reducing quality
                               by any significant amount.

For more information about how these parameters work, see the
[DFTTest documentation](https://github.com/HomeOfVapourSynthEvolution/VapourSynth-DFTTest).

### DPIR

CMDegrain is pretty good, but not good enough, and so I decided to stack it with a much stronger
spatial denoiser - DPIR.

```python
OVERLAP = 8

planes = split(src)
interleaved = core.std.Interleave([
    core.std.Crop(planes[0], 0, src.width // 2 - OVERLAP),
    core.std.Crop(planes[0], src.width // 2 - OVERLAP, 0),
    core.std.AddBorders(core.std.StackVertical(planes[1:]), right=OVERLAP, color=32768)
])
processed = eoe.fmt.process_as(interleaved, partial(DPIR, strength=10, trt=True), "s")
left, right, chroma = processed[::3], processed[1::3], processed[2::3]
left = core.std.Crop(left, 0, OVERLAP)
right = core.std.Crop(right, OVERLAP, 0)
planes[0] = core.std.StackHorizontal([left, right])
planes[1] = core.std.Crop(chroma, 0, OVERLAP, 0, chroma.height // 2)
planes[2] = core.std.Crop(chroma, 0, OVERLAP, chroma.height // 2, 0)

dpir = join(planes)
```

_Note: For whatever reason I didn't have the latest dpir version when writing this, and instead I
used [v1.7.1](https://github.com/HolyWu/vs-dpir/tree/v1.7.1)._

There's quite a lot going on here, so I'll break it down. The main processing is done here:

```python
processed = eoe.fmt.process_as(interleaved, partial(DPIR, strength=10, trt=True), "s")
```

This calls DPIR on a 32-bit floating point ("s" stands for "single precision float") version of the
clip (since DPIR only works on floating point clips).

Unfortunately, DPIR uses a huge amount of VRAM, and processing all three planes as is would use
about three times the amount of VRAM that I have addressable. DPIR has an internal solution to this:
tiling. The idea is to split the clip into tiles, and process each tile independently, one by one.
This effectively halves the amount of VRAM allocated. This does, however, cause an issue where the
border between the two tiles becomes visible after a strong denoise. I solved this by adding a small
overlap between the tiles, currently set to 8 pixels.

Finally, I also decided to denoise the chroma. I still didn't have enough VRAM to do the chroma
planes seperately from the luma, but I realised that since the chroma planes are 1/2 the size of the
luma, I could easily stack them on top of each other, pad one side, and then interleave it with the
luma tiles. As long as the pad colour is neutral (32768 in this case), this doesn't seem to cause
any issues near the borders.

So, to summarise:
- Split the clip into 2 tiles with an 8 pixel overlap
- Add the 2 chroma planes, stacked on top of each other, with 8 pixels of padding, to the tiles
- Interleave the three clips
- Run DPIR on the interleaved clip
- Split the interleaved clip back into three seperate clips
- Crop the overlap off of the left and right tiles
- Split the chroma tile back into two planes, cropping off the overlap padding in the process.
- Join the three planes back together

This effectively saves about 60% of the VRAM allocated by DPIR, without creating much extra
processing, and also without creating any new border/tiling artifacts.

## Detecting the Horizontal Bar Effects

I'm pretty lazy, and generally follow the mantra of "If a task will take me a while to do,
I'll automate it." Most of the time [this is a pretty stupid idea](https://xkcd.com/1319/), and
whilst it can save extra work in the future (e.g. Vivy's denoiser being reused later in the season
without me needing to do anything), It's entirely unnecessary here since I know this issue only
persisted for one episode. Regardless, I couldn't be bothered to go frame by frame and note down
frame ranges, so instead I'll get Vapoursynth to detect the horizontal bar effects for me.

The horizontal bar effect present here might seem difficult to detect at first, but it's actually
fairly simple. The bars are a constant "frequency," and very prevalent, which means that they will
show up very clearly on a fourier transformation. I'm not going to explain exactly what a fourier
transormation is here, or how to read one, but you can read
[the imagemagick documentation](https://legacy.imagemagick.org/Usage/fourier/) for a good overview.

Here's the fourier transformation of the same frame I showed above:

![Frame 5073 - FFT](/assets/cowboy-bebop-s01e23/Bebop_23_5073_fft.png)

The cicled location corresponds to the frequency of the horizontal bar. On frames with the bars,
this will show up on the transformation as a white dot, like here. On normal frames, it will just be
a dark grey. We can then use this point as a reference to detect the horizontal bar effect:

```python
# variable names changed for clarity
def choose_src(src, a, b, thr=180, location=(724, 210)):
    def choose_func(n, f: vs.VideoFrame) -> vs.VideoFrame:
        return a if np.array(f[0], copy=False)[location[1], location[0]] > thr else b

    fft = core.fftspectrum.FFTSpectrum(get_y(clip), False)
    return core.std.FrameEval(src, choose_func, fft, [a, b])
```

What this function does is, for every frame, get the FFT of the frame, and then check the value of
the point at the location specified. If it's above the threshold, it will return the first clip,
otherwise it will return the second clip. This has a pretty much perfect accuracy for detecting the
horizontal bar effect. From there, we can simply use this function to decide which of the two clips
to use for any individual frame.

Since this also doesn't depend on either of the two return clips, it also means that neither of them
have frames requested until after choosing which one we intend to use - which is a very good thing,
because DPIR is not fast, and this script would run at about 0.8fps for the entire thing if both
strong and weak denoisers were always running.

# TL;DR, and summary

Cool denoising with CMDE and DPIR, custom freq_merge, and interesting detection code.

I think that overall this gave a much better result than just leaving the tv sections untouched.
This is obviously not as good quality as the original source, but I'd still say that it's pretty
good, and the process of diagnosing this issue, and then coming up with a way to fix it was fun. The
only reason I encode really is because I just find it exciting to problem solve issues like this.

Hope you found this article interesting. As always, if you have any questions, feel free to contact
me on Discord: @End of Eternity#6292

Cheers, EoE