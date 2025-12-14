import Navbar from "../components/Navbar";
import Section from "../components/Section";
import GamePanel from "../components/GamePanel";

export default function HomePage() {
  return (
    <>
    <Navbar />

    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-4xl font-bold"> Hi, I'm Manas </h1>

      <Section id="about" title="About Me">
        I am a dedicated Computer Science undergraduate with a passion for leveraging technology to solve real-world problems.
        I try to make things, break them sometimes and other times rebuild them, all in the pursuit of learning and innovation.
        This portfolio showcases some of my projects and skills. (That have made it out of my head and messy codebases!)
      </Section>

      <Section id="skills" title="Skills">
          JavaScript, TypeScript, React, Next.js, HTML Canvas, Tailwind-CSS, Solidity, Python, SQL, Java
      </Section>

      <Section id="projects" title="Projects">
        {/* Add projects with brief description here */}
      </Section>

      <GamePanel />
    </main>
    </>
  );
}