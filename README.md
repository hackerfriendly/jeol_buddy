# jeol_buddy.py
Save your microscope parameters to JSON

This script uses the serial port on vintage JEOL scanning electron microscopes
to save beam alignment parameters. Sounds boring, right?

Well it would be if the SEMs of the 1980s had a couple of kilobytes of extra
non-volatile memory. Since they don't, they very parsimoniously only save a
subset of scope parameters, and even then only at one entry per acceleration
voltage. This means wasting hours of time adjusting the beam every time you
want to change the beam current, OL, or several other common scope parameters.

Even more frustratingly, my scope will occasionally decide to reset all
parameters to 0 at boot. For no reason I have yet been able to discern.

Have you ever wanted to compensate for beam skew by automatically recalling
alignment, astig, and focus parameters for a given acceleration voltage at a
given probe current at a given working distance for a given OL selection?

If you understand that sentence at all, you're probably shaking your head in
disbelief. Either your scope already does that for you, or you never knew life
could be so sweet. If it's the latter, You're Welcome.

DISCLAIMER:
  If you break your scope with this script, you get to keep both pieces. Your
  choice to run software you downloaded from the Internet on your vintage
  multi-million dollar instrument is not my problem.

## Hardware

1980s era JEOL SEMs have a female RS232C port on the MPU board. On the JSM-
6320F, it's under the console on the left hand side. You'll want to connect
that to a computer with a serial port (USB to serial adapter should be fine)
via a null modem connection.

If you want to test your connection, run a terminal program (such as minicom)
at 2400 baud, no parity, 8 data bits, 1 stop bit. Hit enter a couple of times
and you should get !3 in response. Congratulations, you're in.

## Running the script

jeol_buddy.py uses the python serial library. If you don't already have it
installed, try 'pip install serial'.

The only option that might need adjustment is --port to specify which serial
port to use. The default is /dev/ttyS0. If that doesn't work, see the top of
the script for suggestions on how to find your serial port.

If all went well, you should be at a > prompt.

The script loads the contents of 'scope.json' at runtime. You can specify a
different location with --config if needed.

## Commands

The main commands are:

  * save       :save all current settings to scope.json
  * status     :show current scope parameters
  * set        :set the SEM parameters to match what has been saved
  * safemode   :set the SEM to a known (probably safe) state

You can also run any JEOL command as if you hit INS on the console. I have not
yet found authoritative documentation for the full command set, but I've
figured out most of the important ones. See reference.txt for details.

**************** E X T R A  S P E C I A L  W A R N I N G ****************

Be careful about typing random commands. Some can cause physical damage to
your scope! You have been warned!

**************** E X T R A  S P E C I A L  W A R N I N G ****************

## Quick start

   1) Bring up an image. Make it nice.
   2) Every time the beam is nicely aligned + astig'd, type 'save'.
   3) Change the accel voltage, probe current, working distance, or OL selection (1-4).
   4) GOTO step 1.

  To recall previously saved settings at any time, type 'set'.

## First Time Workflow

Start by warming up the scope as usual. Connect up the serial cable. You might
get a transient 'serial read error' warning on CRT #2; just ignore it. Bring
up an image at low magnification.

Now run jeol_buddy.py. The supplied scope.json includes settings from a JSM-
6320F, which are almost certainly not the right settings for you. But don't
worry, they are not sent to the SEM until the 'set' command is issued. You can
also just delete scope.json and a new one will be created.

With a decent alignment and focus on the screen, type 'save'. Congratulations,
you just saved your scope parameters to scope.json.

Specifically, jeol_buddy.py saves the following:

  * gun alignment (X + Y beam offsets)
  * OL stigmatism adjust (X + Y)
  * CL stigmatism adjust (X + Y)
  * Objective focus (coarse and fine)

The parameters are all saved together, and indexed like this:

  Acceleration voltage > Probe current (coarse) > WD # > OL selection

If you change any of those parameters, a new "slot" will be saved for
alignment parameters next time you type 'save'.

Note that WD # refers to the working distance number, not the OL coarse/fine
digits. You will end up with settings saved for eg. 6mm, 7mm, 8mm, etc. That
should be close enough to get you within a slight FINE twist of the knob.

## Recalling settings

Now that you have saved some settings, spin the Y beam alignment knob. Watch
the screen go black. Now spin the X knob in the other direction.

Do not despair. Type 'set'.

The image should spring back to the center of the screen, perfectly lit and
aligned. Huzzah!

## Saving more parameters

Now take some time to cycle through all of the parameters you are likely to
change for a given experiment (say, rotate through all probe currents at a
given acceleration voltage), realigning the beam each time you make a change.
Every time the beam is realigned, type 'save'.

Note that for large changes in beam current (and acceleration voltage), the
beam may not return exactly to where it started. You can verify that the X+Y,
astig, etc. are returned to the correct values (hit PF2 or type 'PNU2' to see
for yourself). The amount of drift depends on many black magic analog
parameters, but you should be very close. Try turning the X or Y adjust a
click or two left and right again. The beam should return immediately.

# Notes

Let me know if you find this software useful. It's already saved me hours of
knob twisting and head scratching, but YMMV.

Patches welcome.


--Rob Flickenger
May 2017
