import clsx from 'clsx'

/** The AGENT-P logo (public/logoap.jpg). Also used as the favicon in index.html. */
export const LOGO_SRC = '/logoap.jpg'

export function BrandLogo({ className }: { className?: string }) {
  return <img src={LOGO_SRC} alt="" aria-hidden width={240} height={240} className={clsx('object-cover', className)} />
}
