// Placeholder -- overwritten by JAM compiler on each upload
#include <Mozzi.h>

void setup() {
    startMozzi();
}

void updateControl() {}

AudioOutput updateAudio() {
    return MonoOutput::from8Bit(0);
}

void loop() {
    audioHook();
}
