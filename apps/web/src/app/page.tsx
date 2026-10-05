import { ContactSection } from "@/features/contact/contact-section";
import { ProjectsSection } from "@/features/projects/projects-section";

/**
 * Home. The console and chrome come from the layout; this is the long-form
 * read of the projects and contact that the chat links to.
 */
export default function Page() {
  return (
    <div className="mx-auto w-[min(1000px,100%)] px-[clamp(14px,4vw,40px)]">
      <ProjectsSection />
      <ContactSection />
    </div>
  );
}