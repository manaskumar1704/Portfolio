import Navbar from "../components/Navbar";
import Section from "../components/Section";
import GamePanel from "../components/GamePanel";

export default function HomePage() {
  return (
    <>
      <Navbar />

      <main
        className="min-h-screen bg-black text-white px-8"
        style={{ paddingTop: "calc(var(--navbar-height) + 2.5rem)" }}
      >
        <h1 className="text-4xl font-bold">Hi, I'm Manas</h1>

        <p className="mt-2 text-gray-400 max-w-xl">
          CSE Undergraduate | Web & Game Developer
        </p>

        <Section id="about" title="About Me">
          I am a dedicated Computer Science undergraduate with a passion for leveraging technology to solve real-world problems.
          I try to make things, break them sometimes and other times rebuild them, all in the pursuit of learning and innovation.
          This portfolio showcases some of my projects and skills.
        </Section>

        <Section id="skills" title="Skills">
          JavaScript, TypeScript, React, Next.js, HTML Canvas, Tailwind CSS, Solidity, Python, SQL, Java
        </Section>

        <Section id="projects" title="Projects">
          Test
          {/* Add projects with brief description here */}
        </Section>

        <GamePanel />
      </main>
    </>
  );
}
