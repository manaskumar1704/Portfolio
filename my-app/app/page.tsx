import Navbar from "../components/Navbar";
import Section from "../components/Section";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Separator } from "../components/ui/separator";

import {
  SiJavascript,
  SiTypescript,
  SiReact,
  SiNextdotjs,
  SiTailwindcss,
  SiPython,
  SiSolidity,
  SiMysql,
  SiMongodb,
} from "react-icons/si";

import { FaJava } from "react-icons/fa";
import Skill from "../components/Skill";
import { Github, Linkedin, Mail } from "lucide-react";


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

          <Separator className="my-12" />

          <Section id="about" title="About Me">
            I am a dedicated Computer Science undergraduate with a passion for leveraging technology to solve real-world problems.
            I try to make things, break them sometimes and other times rebuild them, all in the pursuit of learning and innovation.
            This portfolio showcases some of my projects and skills.
          </Section>

          <Separator className="my-12" />

          <Section id="skills" title="Skills">
            <div className="pt-2 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-6">
              <Skill icon={<SiJavascript />} label="JavaScript" />
              <Skill icon={<SiTypescript />} label="TypeScript" />
              <Skill icon={<SiReact />} label="React" />
              <Skill icon={<SiNextdotjs />} label="Next.js" />
              <Skill icon={<SiTailwindcss />} label="Tailwind" />
              <Skill icon={<SiPython />} label="Python" />
              <Skill icon={<SiSolidity />} label="Solidity" />
              <Skill icon={<SiMysql />} label="SQL" />
              <Skill icon={<FaJava />} label="Java" />
              <Skill icon={<SiMongodb />} label="MongoDB" />
            </div>
          </Section>  

          <Separator className="my-12" />

          <Section id="projects" title="Projects">
            Test
            {/* Add projects with brief description here */}
          </Section>
          
          <Separator className="my-12" />
          
          <Section id="contact" title="Contact">
            <p className="mb-4 text-muted-foreground">
              Feel free to reach out for opportunities, collaborations, or just a chat.
            </p>

            <div className="flex items-center gap-6 mt-4">
              <a
                href="mailto:manaskumar1704@gmail.com"
                aria-label="Email"
                className="text-muted-foreground hover:text-accent transition"
              >
                <Mail size={24} />
              </a>
    
              <a
                href="https://github.com/manaskumar1704"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub"
                className="text-muted-foreground hover:text-accent transition"
              >
                <Github size={24} />
              </a>  
    
              <a
                href="https://linkedin.com/in/manas-kumar-372193322"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"
                className="text-muted-foreground hover:text-accent transition"
              >
                <Linkedin size={24} />
              </a>
            </div>

            <Button asChild className="mt-6">
              <a href="/Manas_Kumar_Resume.pdf" download>
                Download Resume
              </a>
            </Button>
          </Section>
        </div>
      </main>
    </>
  );
}
