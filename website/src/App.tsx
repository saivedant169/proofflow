import { MotionConfig } from 'motion/react'
import { LineageRail, Nav } from './components/Chrome'
import Hero from './sections/hero'
import Problem from './sections/problem'
import HowItWorks from './sections/how'
import Demo from './sections/demo'
import Results from './sections/results'
import Architecture from './sections/architecture'
import Evaluation from './sections/evaluation'
import TryIt from './sections/try'

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <a className="skip-link" href="#main">Skip to content</a>
      <Nav />
      <LineageRail />
      <main id="main">
        <Hero />
        <Problem />
        <HowItWorks />
        <Demo />
        <Results />
        <Architecture />
        <Evaluation />
        <TryIt />
      </main>
    </MotionConfig>
  )
}
