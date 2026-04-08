"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Github, Linkedin, Mail } from "lucide-react"

export function ContactSection() {
    const [formState, setFormState] = useState({ name: "", email: "", message: "" })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        const mailtoLink = `mailto:manaskumar1704@gmail.com?subject=Portfolio Inquiry from ${formState.name}&body=${formState.message}%0A%0AFrom: ${formState.email}`
        window.location.href = mailtoLink
    }

    return (
        <section id="contact" className="py-24 px-6 md:px-12 lg:px-24 relative">
            <div className="max-w-7xl mx-auto">
                <span className="text-label-sm text-on-surface-variant tracking-[0.3em]">
                    GET IN TOUCH
                </span>
                <h2 className="font-display text-6xl md:text-7xl lg:text-8xl leading-[0.95] tracking-[-0.04em] uppercase text-on-surface mt-4 mb-16">
                    CONTACT.
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-24">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                    >
                        <p className="text-body-lg text-on-surface-variant mb-8">
                            Open to work at any place that hires me
                        </p>

                        <div className="space-y-6">
                            <a
                                href="mailto:manaskumar1704@gmail.com"
                                className="flex items-center gap-3 text-on-surface hover:text-primary transition-colors"
                            >
                                <Mail className="w-5 h-5" />
                                <span className="text-body-md">manaskumar1704@gmail.com</span>
                            </a>

                            <a
                                href="https://www.linkedin.com/in/manas-kumar1/"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-3 text-on-surface hover:text-primary transition-colors"
                            >
                                <Linkedin className="w-5 h-5" />
                                <span className="text-body-md">linkedin.com/in/manas-kumar1</span>
                            </a>

                            <a
                                href="https://github.com/manaskumar1704"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-3 text-on-surface hover:text-primary transition-colors"
                            >
                                <Github className="w-5 h-5" />
                                <span className="text-body-md">github.com/manaskumar1704</span>
                            </a>
                        </div>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.15 }}
                    >
                        <form 
                            onSubmit={handleSubmit}
                            className="space-y-6"
                        >
                            <div>
                                <label htmlFor="name" className="text-label-sm text-on-surface-variant block mb-2">
                                    Name
                                </label>
                                <input
                                    type="text"
                                    id="name"
                                    name="name"
                                    value={formState.name}
                                    onChange={(e) => setFormState(prev => ({ ...prev, name: e.target.value }))}
                                    className="w-full bg-surface-container-lowest border-b border-outline-variant/15 py-3 px-4 text-on-surface focus:outline-none focus:border-primary transition-colors"
                                    required
                                />
                            </div>

                            <div>
                                <label htmlFor="email" className="text-label-sm text-on-surface-variant block mb-2">
                                    Email
                                </label>
                                <input
                                    type="email"
                                    id="email"
                                    name="email"
                                    value={formState.email}
                                    onChange={(e) => setFormState(prev => ({ ...prev, email: e.target.value }))}
                                    className="w-full bg-surface-container-lowest border-b border-outline-variant/15 py-3 px-4 text-on-surface focus:outline-none focus:border-primary transition-colors"
                                    required
                                />
                            </div>

                            <div>
                                <label htmlFor="message" className="text-label-sm text-on-surface-variant block mb-2">
                                    Message
                                </label>
                                <textarea
                                    id="message"
                                    name="message"
                                    rows={4}
                                    value={formState.message}
                                    onChange={(e) => setFormState(prev => ({ ...prev, message: e.target.value }))}
                                    className="w-full bg-surface-container-lowest border-b border-outline-variant/15 py-3 px-4 text-on-surface focus:outline-none focus:border-primary transition-colors resize-none"
                                    required
                                />
                            </div>

                            <button
                                type="submit"
                                className="w-full py-4 bg-primary-container text-on-primary-container font-display text-sm font-medium tracking-wide uppercase transition-transform duration-300 hover:scale-[1.02]"
                            >
                                Send Message
                            </button>
                        </form>
                    </motion.div>
                </div>
            </div>
        </section>
    )
}
