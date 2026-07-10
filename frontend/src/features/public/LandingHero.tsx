export function LandingHero() {
  return (
    <>
      <h1 className="text-3xl md:text-4xl font-bold text-center mb-3 portal-gradient-text">
        ศูนย์บริการข้อมูลภาครัฐ
      </h1>
      <p className="text-sm md:text-base text-muted-foreground text-center max-w-lg mb-10 leading-relaxed">
        สอบถามข้อมูลจากหน่วยงานภาครัฐได้ครบในที่เดียว —{' '}
        <span className="text-foreground font-medium">Single Portal</span> เพื่อประชาชน
      </p>
    </>
  );
}
