import Navbar from "../components/Navbar";
import Section from "../components/Section";

export default function HomePage() {
  return (
    <>
      <Navbar />

      <main
        className="bg-black text-white px-4 md:px-8 pb-24"
        style={{ paddingTop: "calc(var(--navbar-height) + 2.5rem)" }}
      >
        <div className="max-w-4xl"> 
          <h1 className="text-3xl md:text-4xl font-bold">Hi, I'm Manas</h1>

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

          <Section id="contact" title="Contact">
            <p className="mb-4">I am always open to discussing new opportunities, projects, internships and potential collaborations.</p>

            <ul className="space-y-2">
              <li>
                📧{" "}
                <a href="mailto:manaskumar1704@gmail.com" className="underline hover:text-white">
                  manaskumar1704@gmail.com
                </a>
              </li>

              <li>
                💻{" "}
                <a href="https://github.com/manaskumar1704"target="_blank" rel="noopener noreferrer" className="underline hover:text-white">
                  GitHub
                </a>
              </li>

              <li>
                🔗{" "}
              <a href="https://linkedin.com/in/manas-kumar-372193322" target="_blank" rel="noopener noreferrer" className="underline hover:text-white">
                LinkedIn
              </a>
              </li>
            </ul>

            <a href="/Manas_Kumar_Resume.pdf" download className="inline-block mt-6 bg-white text-black px-6 py-2 rounded-md text-sm hover:bg-gray-200">
              Click here to download my Resume
            </a>
          </Section>
        </div>
      </main>
    </>
  );
}
