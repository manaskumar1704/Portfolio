"use client"

import { useCallback, useEffect, useState, useRef } from "react"
import Image from "next/image"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, Github, Linkedin } from "lucide-react"

interface TypewriterProps {
    text: string
    className?: string
    delay?: number
    cursorClassName?: string
}

function Typewriter({ text, className, delay = 0, cursorClassName = "bg-primary" }: TypewriterProps) {
    const [displayText, setDisplayText] = useState("")
    const [isComplete, setIsComplete] = useState(false)
    const [isPaused, setIsPaused] = useState(false)
    const indexRef = useRef(0)
    const timeoutRef = useRef<NodeJS.Timeout | null>(null)
    const isPausedRef = useRef(false)

    useEffect(() => {
        isPausedRef.current = isPaused
    }, [isPaused])

    useEffect(() => {
        indexRef.current = 0
        
        const startDelay = delay * 1000
        timeoutRef.current = setTimeout(() => {
            const tick = () => {
                if (isPausedRef.current) {
                    timeoutRef.current = setTimeout(tick, 50)
                    return
                }
                
                if (indexRef.current < text.length) {
                    setDisplayText(text.slice(0, indexRef.current + 1))
                    indexRef.current++
                    timeoutRef.current = setTimeout(tick, 50)
                } else {
                    setIsComplete(true)
                }
            }
            tick()
        }, startDelay)

        return () => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current)
        }
    }, [delay, text])

    const handleMouseEnter = useCallback(() => {
        if (!isComplete) setIsPaused(true)
    }, [isComplete])

    const handleMouseLeave = useCallback(() => setIsPaused(false), [])

    return (
        <span 
            className={className}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            {displayText}
            <AnimatePresence>
                {!isComplete && (
                    <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className={`inline-block w-[0.1em] h-[0.9em] align-middle ml-0.5 animate-pulse ${cursorClassName}`}
                    />
                )}
            </AnimatePresence>
        </span>
    )
}

export function HeroSection() {
    const scrollToProjects = useCallback(() => {
        document.getElementById('projects')?.scrollIntoView({ behavior: 'smooth' })
    }, [])

    const [showCursor1, setShowCursor1] = useState(false)
    const [showCursor2, setShowCursor2] = useState(false)

    useEffect(() => {
        const timer1 = setTimeout(() => setShowCursor1(true), 1200)
        const timer2 = setTimeout(() => setShowCursor2(true), 2200)
        return () => {
            clearTimeout(timer1)
            clearTimeout(timer2)
        }
    }, [])

    return (
        <section className="relative min-h-screen flex flex-col justify-center overflow-hidden px-6 md:px-12 lg:px-24 pt-24 pb-16">
            <div className="relative z-10 max-w-7xl mx-auto w-full">
                <div className="flex flex-col lg:flex-row items-center gap-8">
                    <div className="flex-1">
                        <motion.div
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, ease: "easeOut" }}
                            className="flex items-center gap-2"
                        >
                            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                            <span className="text-label-md text-on-surface-variant tracking-[0.2em]">
                                AVAILABLE FOR WORK
                            </span>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.8, delay: 0.15, ease: "easeOut" }}
                            className="mt-6 md:mt-10"
                        >
                            <h1 className="font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl xl:text-8xl leading-[0.95] tracking-[-0.04em] uppercase text-on-surface">
                                <Typewriter text="Manas" delay={0.3} />{" "}
                                <span className="text-primary">
                                    <Typewriter text="Kumar" delay={0.8} />
                                </span>
                                {showCursor1 && (
                                    <motion.span
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="inline-block w-[0.1em] h-[0.9em] align-middle ml-1 bg-primary animate-pulse"
                                    />
                                )}
                            </h1>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.8, delay: 0.25, ease: "easeOut" }}
                            className="mt-6 md:mt-10"
                        >
                            <h2 className="font-display text-2xl sm:text-3xl md:text-4xl lg:text-5xl xl:text-6xl leading-[0.95] tracking-[-0.04em] uppercase text-on-surface">
                                <Typewriter text="Building Production Grade" delay={1.3} />
                                <br />
                                <span className="hidden sm:inline">
                                    <Typewriter text="Agentic Systems." delay={1.8} />
                                </span>
                                <span className="sm:hidden">
                                    <Typewriter text="Agentic Systems" delay={1.8} />
                                </span>
                                {showCursor2 && (
                                    <motion.span
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="inline-block w-[0.1em] h-[0.9em] align-middle ml-1 animate-pulse"
                                    />
                                )}
                            </h2>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.7, delay: 0.35, ease: "easeOut" }}
                            className="mt-6 md:mt-8"
                        >
                            <p className="text-body-lg text-on-surface-variant max-w-xl">
                                Open To
                            </p>
                            <p className="text-xl md:text-2xl font-display text-primary mt-1">
                                GenAI . AgenticAI . Full-Stack . SDE . AI Engineer
                            </p>
                            <p className="text-body-lg text-on-surface-variant mt-4 max-w-xl">
                                Roles
                            </p>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.7, delay: 0.45, ease: "easeOut" }}
                            className="mt-10 md:mt-14 flex flex-wrap items-center gap-4 sm:gap-6"
                        >
                            <button
                                onClick={scrollToProjects}
                                suppressHydrationWarning
                                className="group inline-flex items-center gap-3 px-6 py-3 bg-primary-container text-on-primary-container font-display text-sm font-medium tracking-wide transition-transform duration-300 hover:scale-[1.02]"
                            >
                                View Projects
                                <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
                            </button>

                            <a
                                href="/Manas_Kumar_Resume _SDE.pdf"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="group inline-flex items-center gap-3 px-6 py-3 border border-white/10 text-on-surface font-display text-sm font-medium tracking-wide transition-all duration-300 hover:bg-white/5"
                            >
                                Download Resume
                            </a>

                            <div className="flex items-center gap-1 sm:gap-2 flex-nowrap">
                                <a
                                    href="https://github.com/manaskumar1704"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="p-3 text-on-surface-variant hover:text-on-surface transition-colors duration-300"
                                >
                                    <Github className="w-5 h-5" />
                                </a>

                                <a
                                    href="https://www.linkedin.com/in/manas-kumar1/"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="p-3 text-on-surface-variant hover:text-on-surface transition-colors duration-300"
                                >
                                    <Linkedin className="w-5 h-5" />
                                </a>
                            </div>
                        </motion.div>
                    </div>

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.8, delay: 0.3 }}
                        className="lg:hidden w-full max-w-[300px] mx-auto aspect-[3/4] overflow-hidden rounded-lg"
                    >
                        <Image
                            src="/images/projects/my_image.png"
                            alt="Manas Kumar"
                            width={400}
                            height={533}
                            quality={90}
                            sizes="100vw"
                            className="w-full h-full object-cover object-top grayscale opacity-80"
                        />
                    </motion.div>
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.8, delay: 0.3 }}
                        className="hidden lg:block lg:w-[320px] flex-shrink-0"
                    >
                        <div className="relative w-full aspect-[3/4] overflow-hidden rounded-lg group">
                            <Image
                                src="/images/projects/my_image.png"
                                alt="Manas Kumar"
                                width={320}
                                height={427}
                                quality={90}
                                priority
                                className="w-full h-full object-cover object-top grayscale opacity-80 group-hover:grayscale-0 group-hover:scale-105 group-hover:opacity-100 transition-all duration-700"
                            />
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    )
}