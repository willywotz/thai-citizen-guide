interface AppLogoProps {
  src?: string;
  alt?: string;
  className?: string;
}

export function AppLogo({ src = "/logo.png", alt = "Logo", className = "" }: AppLogoProps) {
  return (
    <div className={className}>
      <img src={src} alt={alt} className={`rounded-lg object-contain w-full h-full`} />
    </div>
  );
}
