import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: 'Write Music as Code',
    description: (
      <>
        Define instruments, sequences, patterns, and arrangements in readable
        <code>.jam</code> files. Synths, drums, effects, LFOs, chords — all
        in a clean DSL.
      </>
    ),
  },
  {
    title: 'Compile to Hardware',
    description: (
      <>
        Generates Mozzi 2.0 C++ sketches for ESP32 and Arduino. Upload via
        PlatformIO and hear your code play through real speakers.
      </>
    ),
  },
  {
    title: 'Preview in Browser',
    description: (
      <>
        Render WAV audio without any hardware. The web editor compiles and
        plays your music instantly — perfect for prototyping.
      </>
    ),
  },
];

function Feature({title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center padding-horiz--md" style={{paddingTop: '2rem'}}>
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
