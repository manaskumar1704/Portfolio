import { HeroSection } from "../components/sections/HeroSection";
import { AboutSection } from "../components/sections/AboutSection";
import { SkillsSection } from "../components/sections/SkillsSection";
import { ProjectsSection } from "../components/sections/ProjectsSection";
import { ExperienceSection } from "../components/sections/ExperienceSection";
import { ContactSection } from "../components/sections/ContactSection";
import { FloatingDock } from "../components/sections/FloatingDock";

export default function Home() {
  return (
    <main className="min-h-screen bg-surface text-on-surface selection:bg-primary/30 selection:text-white pb-20 md:pb-0">
      <HeroSection />
      <AboutSection />
      <SkillsSection />
      <ProjectsSection />
      <ExperienceSection />
      <ContactSection />
      <FloatingDock />
    </main>
  );
}
