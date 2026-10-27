import { useEffect, useRef } from 'react'

const PLAYBACK_RATE = 0.6

/**
 * Frosted, slowed-down background video. The video is drawn at half the viewport size, blurred there, and
 * scaled up: the blur costs ~4x less GPU than blurring a full-screen layer, and the softness hides detail.
 */
export function VideoBackground({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = ref.current
    if (!video) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const apply = () => {
      video.playbackRate = PLAYBACK_RATE
      if (reduced) video.pause()
    }
    apply()
    video.addEventListener('loadedmetadata', apply)
    video.addEventListener('play', apply)
    return () => {
      video.removeEventListener('loadedmetadata', apply)
      video.removeEventListener('play', apply)
    }
  }, [])

  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden>
      <video
        ref={ref}
        className="landing-video absolute left-1/4 top-1/4 h-1/2 w-1/2 object-cover"
        src={src}
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        disablePictureInPicture
      />
      {/* Darkening + glass sheen so the motion reads as soft light, not footage. */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_55%,rgb(1_2_10/72%),rgb(1_2_10/35%)_55%,rgb(1_2_10/60%))]" />
      <div className="absolute inset-0 bg-[linear-gradient(115deg,rgb(255_255_255/4%),transparent_35%,transparent_65%,rgb(120_160_255/5%))]" />
    </div>
  )
}
