export function LandingHero() {
  return (
    <>
      <div className="relative mb-8">
        <div className="absolute inset-0 w-24 h-24 rounded-3xl gov-gradient opacity-30 blur-xl scale-125" />
        <div className="relative w-24 h-24 rounded-3xl gov-gradient flex items-center justify-center text-white text-4xl font-bold shadow-xl">
          AI
        </div>
      </div>
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
