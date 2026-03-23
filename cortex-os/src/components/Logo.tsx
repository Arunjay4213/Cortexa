import { motion } from 'motion/react'

export function Logo({ className = 'logo-img-nav' }: { className?: string }) {
  return (
    <motion.img
      src={`${import.meta.env.BASE_URL}cortexalogo.jpeg`}
      alt="Cortexa"
      className={`${className} rounded-lg`}
      animate={{
        filter: [
          'drop-shadow(0 0 0px rgba(122,140,0,0))',
          'drop-shadow(0 0 14px rgba(122,140,0,0.4))',
          'drop-shadow(0 0 0px rgba(122,140,0,0))',
        ],
      }}
      transition={{ duration: 3.5, ease: 'easeInOut', repeat: Infinity }}
    />
  )
}
