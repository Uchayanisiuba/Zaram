\# Zaram UI \& Experience Guidelines



Version: 1.0



Status: Living Document



Project: Zaram AI Operating System



Owner: Uche Anisiuba



Repository:

https://github.com/Uchayanisiuba/Zaram



Related Documents



\- 00\_PROJECT\_BIBLE.md

\- 01\_ARCHITECTURE.md

\- 03\_MODEL\_ROUTER.md

\- 05\_VOICE\_ENGINE.md



\---



\# Document Purpose



This document defines the visual identity, interaction principles, animation standards, accessibility requirements, and user experience philosophy for the Zaram AI Operating System.



Every screen, component, animation, and interaction should follow these guidelines to ensure a consistent premium experience.



\---



\# Design Philosophy



Zaram is not designed like traditional software.



It should feel like interacting with a living digital intelligence.



The interface must communicate:



\- Intelligence

\- Calmness

\- Precision

\- Confidence

\- Elegance



Every visual decision should reinforce the feeling that the user is interacting with an advanced AI operating system.



\---



\# Design Principles



Every interface should be:



• Minimal



• Premium



• Cinematic



• Responsive



• Fluid



• Accessible



• Modern



• Purposeful



If an element does not improve usability or understanding, it should be removed.



\---



\# Visual Identity



The overall aesthetic combines:



\- Glassmorphism

\- Soft gradients

\- Ambient lighting

\- Dynamic motion

\- High contrast

\- Clean typography

\- Transparent layers



The interface should never appear flat or cluttered.



\---



\# Color System



\## Primary Background



Near Black



Purpose



Allow the Orb and future MetaHuman to become the visual focus.



\---



\## Glass Panels



Transparent



Blurred



Soft border



Subtle reflections



Rounded corners



Opacity should remain between 45–70%.



\---



\## Accent Colors



Accent colors are controlled by AI state.



The interface should never use random colors.



Every accent communicates system status.



\---



\# Orb State Colors



\## Idle



Primary



Blue



Purpose



Calm



Available



Waiting



\---



\## Listening



Primary



Cyan



Purpose



Receiving user input



Orb becomes brighter.



Movement increases slightly.



\---



\## Thinking



Primary



Purple



Purpose



Reasoning



Problem solving



Internal energy rotation increases.



\---



\## Generating



Primary



White



Secondary



Blue



Purpose



Generating responses.



Orb expands.



Energy increases.



\---



\## Speaking



Primary



Blue



Secondary



Cyan



Purpose



Audio playback



Orb reacts directly to speech amplitude.



Glow intensity follows voice volume.



\---



\## Creative



Primary



Purple



Secondary



Gold



Purpose



Creative generation



Brainstorming



Image generation



Design work



\---



\## Working



Primary



Orange



Purpose



Executing tools



Processing documents



Running code



\---



\## Error



Primary



Red



Purpose



Failures



Warnings



Unexpected states



Motion becomes unstable before smoothly returning to Idle.



\---



\# Orb Behaviour



The Orb is the heart of the interface.



It should never appear static.



Idle behaviour includes:



\- Slow breathing

\- Floating motion

\- Gentle rotation

\- Ambient deformation



Speaking behaviour includes:



\- Audio FFT deformation

\- Pulse synchronized with speech

\- Dynamic glow

\- Particle emission



Listening behaviour includes:



\- Attraction toward microphone activity

\- Increased brightness

\- Responsive motion



The Orb should feel alive rather than animated.



\---



\# Animation Guidelines



Animation exists to communicate state.



Never animate simply for decoration.



\---



\## Timing



Micro feedback



100–200 ms



Standard transitions



250–400 ms



Large transitions



500–800 ms



Orb state changes



600–1500 ms



Animations should feel smooth and organic.



\---



\# Motion Language



Preferred motion



Ease In Out



Spring



Natural acceleration



Soft overshoot



Avoid:



Abrupt movement



Linear interpolation



Sudden scaling



Harsh rotations



\---



\# Layout Principles



Use a layered composition.



```

Background



↓



Environment



↓



Orb



↓



Glass Panels



↓



Floating Components



↓



Notifications



↓



Dialogs

```



Future MetaHuman rendering sits between Environment and Orb.



\---



\# Chat Interface



The chat workspace is the primary user experience.



Layout



Sidebar



↓



Conversation



↓



Input Bar



Input Bar Components



```

+-----------------------------------------------------------+



\[Upload]  Text Input.................... \[Mic] \[Send/Stop]



+-----------------------------------------------------------+

```



Requirements



Document Upload button



Left aligned



Text input expands automatically



Microphone button



Immediately left of Send button



Send button transforms into Stop button while AI is generating



Conversation should remain centered and highly readable.



\---



\# Voice Interaction



When user begins speaking



AI immediately stops speaking.



Orb changes to Listening.



Microphone button animates.



Speech begins processing.



When AI responds



Orb changes to Speaking.



Send button becomes Stop.



Speech streams immediately.



\---



\# Typography



Primary Font



Inter



Fallback



System UI



Typography should prioritize readability.



Avoid decorative fonts.



Consistent spacing between headings and content.



\---



\# Icons



Use minimal outlined icons.



Prefer Lucide icons.



Icons inherit AI accent color where appropriate.



Avoid filled icons unless communicating destructive actions.



\---



\# Spacing System



Base spacing



4px



Scale



4



8



12



16



24



32



48



64



96



Whitespace is an intentional design element.



\---



\# Responsive Behaviour



Support



Desktop



Ultrawide



Laptop



Tablet (future)



AR



VR



Avoid hardcoded dimensions.



Prefer flexible layouts.



\---



\# Accessibility



Support keyboard navigation.



Maintain sufficient contrast.



Respect reduced-motion preferences.



Provide descriptive labels for assistive technologies.



Animations must never reduce usability.



\---



\# Performance



Maintain 60 FPS.



GPU accelerated animations.



Minimize unnecessary React re-renders.



Lazy load heavy components.



Virtualize long conversations.



Optimize animation loops.



\---



\# Future Vision



The UI should eventually support:



Interactive MetaHuman



3D environments



Spatial interfaces



Gesture interaction



Eye tracking



AR overlays



VR workspaces



The visual language established today should naturally extend into immersive experiences.



\---



\# Definition of Success



A successful Zaram interface should feel instantly recognizable.



Without reading any text, a user should understand:



\- What the AI is doing

\- Whether it is listening

\- Whether it is thinking

\- Whether it is speaking

\- Whether something has gone wrong



The interface should communicate intelligence through motion, lighting, transparency, and interaction rather than excessive visual complexity.

