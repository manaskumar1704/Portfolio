"use client";

import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import ProjectCard from "../components/ProjectCard";
import SiteCard from "../components/SiteCard";
import Skill from "../components/Skill";
import { Button } from "../components/ui/button";
import { motion } from "framer-motion";

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
import { FaJava, FaHammer } from "react-icons/fa";
import { ArrowRight, Download, Phone, Github, Linkedin, Mail } from "lucide-react";

const projects = [
  {
    title: "ChainForge 2.0",
    description: "Cryptographically prove the existence of digital files.",
    tags: ["React", "Ethereum", "Crypto", "Web3"],
    repoLink: "https://github.com/manaskumar1704/ChainForge2.0",
    demoLink: "https://chain-forge2-0.vercel.app/",
  },
  {
    title: "Portfolio Website",
    description: "My personal digital garden. Built with Next.js 15, Tailwind V4, and Framer Motion.",
    tags: ["Next.js", "React", "Tailwind CSS", "Framer Motion"],
    repoLink: "https://github.com/manaskumar1704/Portfolio",
    demoLink: "https://manas.dev",
  },
];

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 }
};

const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.1
    }
  }
};

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background relative selection:bg-primary/20 selection:text-primary">
      {/* Background Elements */}
      <div className="fixed inset-0 -z-10 h-full w-full bg-background [background:radial-gradient(125%_125%_at_50%_10%,#000_40%,#63e_100%)] opacity-20 pointer-events-none" />

      <Navbar />

      <main className="container mx-auto px-4 pt-32 pb-16 space-y-32">
        {/* Hero Section */}
        <section id="home" className="min-h-[60vh] flex flex-col justify-center items-start max-w-4xl mx-auto">
          <motion.div
            initial="initial"
            animate="animate"
            variants={staggerContainer}
            className="space-y-6"
          >
            <motion.div variants={fadeInUp} className="inline-block rounded-full bg-secondary/50 px-3 py-1 text-sm font-medium text-primary ring-1 ring-inset ring-primary/20">
              Available for work
            </motion.div>

            <motion.h1 variants={fadeInUp} className="text-5xl md:text-7xl font-extrabold tracking-tight">
              Hi, I&apos;m <span className="bg-clip-text text-transparent bg-gradient-to-r from-primary to-purple-400">Manas</span>
              <br />
              <span className="text-foreground/80">I build things.</span>
            </motion.h1>

            <motion.p variants={fadeInUp} className="text-xl text-muted-foreground max-w-2xl leading-relaxed">
              I&apos;m a Computer Science undergraduate focused on building accessible, pixel-perfect, and performant web experiences.
            </motion.p>

            <motion.div variants={fadeInUp} className="flex gap-4 pt-4">
              <Button size="lg" className="rounded-full text-base font-semibold px-8" asChild>
                <a href="#projects">
                  View Work <ArrowRight className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button variant="outline" size="lg" className="rounded-full text-base px-8" asChild>
                <a href="/Manas_Kumar_Resume.pdf" download>
                  Resume <Download className="ml-2 h-4 w-4" />
                </a>
              </Button>
            </motion.div>
          </motion.div>
        </section>

        {/* About Section */}
        <motion.section
          id="about"
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.7 }}
          className="max-w-4xl mx-auto"
        >
          <div className="flex flex-col md:flex-row gap-12 items-center">
            <div className="flex-1 space-y-6">
              <h2 className="text-3xl font-bold flex items-center gap-3">
                <span className="text-primary font-mono text-xl">01.</span> About Me
              </h2>
              <div className="glass-card p-8 rounded-2xl space-y-4 text-muted-foreground leading-relaxed border-l-4 border-primary/50">
                <p>
                  I&apos;m a Computer Science undergrad who turns caffeine into code and ambitious ideas into digital reality.
                  I thrive on the thrill of building systems, breaking them (occasionally on purpose), and rebuilding them stronger.
                </p>
                <p>
                  What started as tinkering with static HTML has evolved into crafting robust full-stack applications.
                  I&apos;m constantly chasing the perfect balance between clean aesthetics and functionality.
                </p>
              </div>
            </div>
            {/* Can add a profile image here later */}
          </div>
        </motion.section>

        {/* Skills Section */}
        <section id="skills" className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="text-3xl font-bold mb-12 flex items-center gap-3">
              <span className="text-primary font-mono text-xl">02.</span> Tech Stack
            </h2>

            <div className="space-y-12">
              {/* Languages */}
              <div>
                <h3 className="text-xl font-semibold mb-6 flex items-center gap-2 text-foreground/80 pl-2 border-l-2 border-primary">Languages</h3>
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-8 p-8 glass rounded-2xl border-t border-white/5">
                  <Skill icon={<SiJavascript />} label="JavaScript" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<SiTypescript />} label="TypeScript" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<SiPython />} label="Python" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<SiSolidity />} label="Solidity" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<SiMysql />} label="SQL" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<FaJava />} label="Java" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                </div>
              </div>

              {/* Frameworks & Tools */}
              <div>
                <h3 className="text-xl font-semibold mb-6 flex items-center gap-2 text-foreground/80 pl-2 border-l-2 border-primary">Frameworks & Tools</h3>
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-8 p-8 glass rounded-2xl border-t border-white/5">
                  <Skill icon={<SiReact />} label="React" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<SiNextdotjs />} label="Next.js" className="hover:text-foreground dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<SiTailwindcss />} label="Tailwind" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<SiMongodb />} label="MongoDB" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                  <Skill icon={<FaHammer />} label="Hardhat" className="hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-300 transform hover:scale-110" />
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        {/* Projects Section */}
        <section id="projects" className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="text-3xl font-bold mb-12 flex items-center gap-3">
              <span className="text-primary font-mono text-xl">03.</span> Featured Projects
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {projects.map((project, index) => (
                <ProjectCard key={index} {...project} />
              ))}
            </div>
          </motion.div>
        </section>

        {/* Sites I Frequent Section */}
        <section id="sites" className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="text-3xl font-bold mb-12 flex items-center gap-3">
              <span className="text-primary font-mono text-xl">04.</span> Sites I Frequent
            </h2>
            <p className="text-muted-foreground mb-8 max-w-2xl">
              A curated list of websites I visit daily for inspiration, resources, and learning.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                {
                  name: "Build Your Own X",
                  url: "https://github.com/codecrafters-io/build-your-own-x",
                  category: "Learning",
                  description: "Master programming by recreating your favorite technologies from scratch.",
                },
                {
                  name: "Overleaf",
                  url: "https://www.overleaf.com/",
                  category: "Writing",
                  description: "Collaborative LaTeX editor for academic writing.",
                },
                {
                  name: "Gemini",
                  url: "https://gemini.google.com/",
                  category: "AI",
                  description: "Advanced AI assistance for coding and creativity.",
                },
                {
                  name: "Pinata IPFS",
                  url: "https://www.pinata.cloud/",
                  category: "Web3",
                  description: "IPFS pinning service for decentralized storage.",
                },
                {
                  name: "Sepolia PoW Faucet",
                  url: "https://sepolia-faucet.pk910.de/",
                  category: "Web3",
                  description: "Mining faucet for Sepolia testnet ETH.",
                },
                {
                  name: "Docs to Markdown",
                  url: "https://www.docstomarkdown.pro/convert-word-to-markdown/",
                  category: "Utility",
                  description: "Convert Word documents to clean Markdown.",
                },
                {
                  name: "Vercel",
                  url: "https://vercel.com",
                  category: "Deployment",
                  description: "My go-to platform for deploying Next.js apps.",
                },
                {
                  name: "ui.shadcn.com",
                  url: "https://ui.shadcn.com",
                  category: "UI Library",
                  description: "Beautifully designed components.",
                },
                {
                  name: "Framer Motion",
                  url: "https://www.framer.com/motion/",
                  category: "Animation",
                  description: "The best React animation library.",
                },
              ].map((site, index) => (
                <SiteCard key={index} {...site} />
              ))}
            </div>
          </motion.div>
        </section>

        {/* Contact Section */}
        <section id="contact" className="max-w-3xl mx-auto text-center py-20">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="glass-card p-12 rounded-3xl relative overflow-hidden group"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <p className="text-primary font-mono mb-4 text-lg relative z-10">05. What&apos;s Next?</p>
            <h2 className="text-4xl md:text-5xl font-bold mb-6 relative z-10">Get In Touch</h2>
            <p className="text-lg text-muted-foreground mb-10 max-w-xl mx-auto relative z-10">
              I&apos;m currently looking for new opportunities. Whether you have a question or just want to say hi, I&apos;ll try my best to get back to you!
            </p>

            <div className="flex flex-col items-center gap-6 relative z-10">
              <div className="flex flex-col items-center gap-3">
                <div className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors group/email">
                  <Mail size={20} className="group-hover/email:scale-110 transition-transform" />
                  <a href="mailto:manaskumar1704@gmail.com" className="text-xl font-medium">manaskumar1704@gmail.com</a>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors group/phone">
                  <Phone size={20} className="group-hover/phone:scale-110 transition-transform" />
                  <span className="text-xl font-medium">+91 8796955365</span>
                </div>
              </div>

              <div className="flex gap-6 mt-6">
                <a href="https://github.com/manaskumar1704" target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground transition-colors transform hover:scale-110">
                  <Github size={32} />
                </a>
                <a href="https://linkedin.com/in/manas-kumar-372193322" target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-[#0077b5] transition-colors transform hover:scale-110">
                  <Linkedin size={32} />
                </a>
              </div>
            </div>
          </motion.div>
        </section>

      </main>

      <Footer />
    </div>
  );
}
