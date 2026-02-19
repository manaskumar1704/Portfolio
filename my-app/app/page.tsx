import { HeroSection } from "../components/sections/HeroSection";
import { SkillsSection } from "../components/sections/SkillsSection";
import { ProjectsSection } from "../components/sections/ProjectsSection";

export default function Home() {
  return (
    <main className="min-h-screen bg-obsidian text-foreground selection:bg-reiatsu/30 selection:text-white">
      {/* Introduction */}
      <HeroSection />

      {/* Expertise */}
      <SkillsSection />

      {/* Works */}
      <ProjectsSection />

      {/* Footer / Final Call to Action */}
      <footer className="py-12 text-center text-sm text-gray-600 font-mono border-t border-white/5">
        <p>© 2026 MANAS. ARCHITECTING REALITIES.</p>
      </footer>
    </main>
  );
}
