import { HeroSection } from "../components/sections/HeroSection";
import { AboutSection } from "../components/sections/AboutSection";
import { SkillsSection } from "../components/sections/SkillsSection";
import { ProjectsSection } from "../components/sections/ProjectsSection";
import { FloatingDock } from "../components/sections/FloatingDock";

export default function Home() {
  return (
    <main className="min-h-screen bg-surface text-on-surface selection:bg-primary/30 selection:text-white">
      <HeroSection />
      <ProjectsSection />
      <AboutSection />
      <SkillsSection />

      {/* Contact / CTA Section */}
      <section id="contact" className="py-24 px-6 md:px-12 lg:px-24 bg-surface-container-lowest">
        <div className="max-w-7xl mx-auto">
          <div className="bg-surface-container p-12 md:p-16 flex flex-col md:flex-row md:items-center md:justify-between gap-8">
            <div>
              <h2 className="text-display-sm text-on-surface">
                START A
                <br />
                PROJECT.
              </h2>
              <p className="text-body-md text-on-surface-variant mt-4 max-w-md">
                Currently accepting select editorial and engineering commissions for 2024. Let&apos;s build something monolithic.
              </p>
            </div>
            <button className="inline-flex items-center px-8 py-4 bg-primary-container text-on-primary-container font-display text-sm font-medium tracking-wider uppercase transition-transform duration-300 hover:scale-[1.02] shrink-0">
              INQUIRY REQUEST
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 md:px-12 lg:px-24 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <span className="font-display font-bold text-on-surface tracking-tight">
              DEV/EDITORIAL
            </span>
            <p className="text-label-sm text-on-surface-variant/40 mt-1">
              ARCHITECTURAL ENGINEERING
            </p>
          </div>
          <div className="flex items-center gap-8">
            {["GITHUB", "LINKEDIN", "READCV", "TWITTER"].map((link) => (
              <a
                key={link}
                href="#"
                className="text-label-sm text-on-surface-variant/40 hover:text-on-surface-variant transition-colors tracking-wider"
              >
                {link}
              </a>
            ))}
          </div>
          <span className="text-label-sm text-on-surface-variant/30">
            ©2024 ARCHITECTURAL MONOLITH. ALL RIGHTS RESERVED.
          </span>
        </div>
      </footer>

      <FloatingDock />
    </main>
  );
}
