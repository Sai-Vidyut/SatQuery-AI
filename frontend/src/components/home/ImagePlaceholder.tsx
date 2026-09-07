import Image from "next/image";

type ImagePlaceholderProps = {
  src?: string;
  alt: string;
  label?: string;
  className?: string;
  variant?: "default" | "compact" | "hero";
};

export function ImagePlaceholder({
  src,
  alt,
  label,
  className = "",
  variant = "default",
}: ImagePlaceholderProps) {
  if (src) {
    return (
      <div
        className={`home-about__image home-about__image--${variant} ${className}`.trim()}
      >
        <Image
          src={src}
          alt={alt}
          fill
          className="home-about__image-media"
          sizes={
            variant === "hero"
              ? "(max-width: 1023px) 100vw, 600px"
              : variant === "default"
                ? "(max-width: 767px) 100vw, 480px"
                : "(max-width: 767px) 100vw, 400px"
          }
        />
      </div>
    );
  }

  return (
    <div
      className={`home-placeholder home-placeholder--${variant} ${className}`.trim()}
      role="img"
      aria-label={label ?? alt}
    >
      {label ? <span className="home-placeholder__label">{label}</span> : null}
    </div>
  );
}
