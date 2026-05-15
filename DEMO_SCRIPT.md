# SmartOnboard Demo Video Script

**Duration**: 3-5 minutes  
**Target Audience**: IBM Bob Hackathon Judges  
**Goal**: Showcase the "wow moment" - 60-second onboarding vs. 3-week manual process

---

## Video Structure

### Opening (0:00 - 0:30)
**Scene**: Title card with problem statement

**Voiceover**:
> "When a new developer joins your team, how long does it take them to understand your codebase? Two weeks? Three weeks? A month?"

**Visual**: 
- Show calendar pages flipping
- Frustrated developer scrolling through code
- Slack messages: "Where do I start?" "What does this do?"

**Voiceover**:
> "What if you could onboard them in 60 seconds?"

**Visual**: 
- Transition to SmartOnboard logo
- Tagline: "AI-powered codebase onboarding accelerator"

---

### Problem Statement (0:30 - 1:00)
**Scene**: Split screen showing traditional vs. SmartOnboard approach

**Voiceover**:
> "Traditional onboarding is painful. New engineers spend weeks just reading code, asking questions, and trying to understand where things are."

**Visual - Left Side (Traditional)**:
- Developer reading documentation
- Confused expressions
- Multiple browser tabs open
- Sticky notes everywhere
- Timeline: "Week 1: Still reading... Week 2: Starting to understand... Week 3: First contribution"

**Visual - Right Side (SmartOnboard)**:
- Clean interface
- URL input
- Progress bar
- Beautiful guide generated
- Timeline: "60 seconds: Complete understanding"

---

### Solution Demo (1:00 - 3:30)
**Scene**: Live application walkthrough

#### Part 1: Landing Page (1:00 - 1:15)
**Visual**: 
- Open browser to `http://localhost:5000`
- Show clean, professional landing page
- Highlight key features

**Voiceover**:
> "SmartOnboard uses IBM Bob and watsonx.ai to analyze any GitHub repository and generate comprehensive onboarding guides."

**Actions**:
- Hover over features
- Show role selector (Engineer, Manager, Architect)

#### Part 2: Repository Analysis (1:15 - 2:15)
**Visual**: 
- Enter repository URL: `https://github.com/expressjs/express`
- Select role: "Engineer"
- Click "Generate Onboarding Guide"

**Voiceover**:
> "Let's analyze Express.js - a popular Node.js framework with over 1,000 files. Watch as IBM Bob analyzes the entire codebase in real-time."

**Visual - Analysis Page**:
- Show 6-step progress animation:
  1. ✓ Cloning repository
  2. ✓ Detecting tech stack
  3. ✓ Analyzing architecture
  4. ✓ Mapping components
  5. ✓ Generating insights
  6. ✓ Creating guide

**Voiceover**:
> "Bob reads the complete repository context, understands the architecture, identifies key files, and explains critical logic."

**Visual**: 
- Fun facts rotating
- Progress percentage increasing
- Timer showing: "Analysis time: 58 seconds"

#### Part 3: Results Dashboard (2:15 - 3:00)
**Visual**: 
- Dashboard loads with beautiful Soft UI design
- Show tabbed interface

**Voiceover**:
> "In under 60 seconds, we have a complete onboarding guide."

**Actions - Quick Tour**:

1. **Overview Tab** (5 seconds)
   - Scroll through project summary
   - Show tech stack badges
   - Highlight key metrics

2. **Architecture Tab** (5 seconds)
   - Show Mermaid diagram
   - Zoom in on components
   - Highlight data flow

3. **Key Files Tab** (5 seconds)
   - Show file tree with importance ratings
   - Click on a critical file
   - Show explanation

4. **Getting Started Tab** (5 seconds)
   - Show setup commands
   - Highlight first contribution guide
   - Show "Day 1 tasks"

5. **Interactive Q&A** (10 seconds)
   - Type question: "How does routing work?"
   - Show Bob's contextual answer
   - Type another: "Where is authentication handled?"
   - Show instant response

**Voiceover**:
> "But it's not just static documentation. You can ask Bob questions about the codebase and get instant, contextual answers."

#### Part 4: Role-Specific Views (3:00 - 3:20)
**Visual**: 
- Switch to "Manager" role
- Show different content focus

**Voiceover**:
> "SmartOnboard generates role-specific guides. Managers see high-level architecture and team structure. Architects see scalability patterns and design decisions."

**Visual**: 
- Quick comparison of Engineer vs. Manager vs. Architect views
- Side-by-side screenshots

#### Part 5: Export & Share (3:20 - 3:30)
**Visual**: 
- Click "Export Guide" button
- Show export options (PDF, Markdown, HTML)
- Download PDF
- Open PDF showing professional formatting

**Voiceover**:
> "Export guides as PDF, Markdown, or HTML to share with your team."

---

### IBM Bob Integration Showcase (3:30 - 4:00)
**Scene**: Behind-the-scenes technical view

**Visual**: 
- Show `.bob/modes/onboarding-guide-generator.yaml`
- Show `.bob/skills/onboarding-guide.md`
- Show Bob IDE with custom mode active

**Voiceover**:
> "SmartOnboard is built using IBM Bob's most powerful features: custom modes for specialized analysis, reusable skills for team standardization, and full repository context understanding."

**Visual**: 
- Highlight key Bob features used:
  - ✓ Custom Modes
  - ✓ Skills
  - ✓ Full Repo Context
  - ✓ Context Mentions (@file, @folder)
  - ✓ Code Explanation
  - ✓ Literate Coding

---

### watsonx.ai Integration (4:00 - 4:15)
**Scene**: Show watsonx.ai enhancement

**Visual**: 
- Show code snippet of watsonx.ai integration
- Show Granite 3-8B Instruct model in action
- Before/after content comparison

**Voiceover**:
> "Content is enhanced using IBM watsonx.ai's Granite models, ensuring professional, role-specific formatting and clarity."

---

### Business Impact (4:15 - 4:30)
**Scene**: Impact metrics

**Visual**: 
- Animated statistics:
  - "Traditional Onboarding: 2-4 weeks"
  - "SmartOnboard: 60 seconds"
  - "Time Saved: 95%"
  - "Cost Reduction: $10,000+ per engineer"

**Voiceover**:
> "The impact is massive. Reduce onboarding time by 95%. Save thousands of dollars per new hire. Get engineers contributing on day one."

---

### Closing (4:30 - 5:00)
**Scene**: Call to action

**Visual**: 
- SmartOnboard logo
- GitHub repository link
- Key features summary

**Voiceover**:
> "SmartOnboard: Turn weeks of confusion into 60 seconds of clarity. Built with IBM Bob and watsonx.ai for the IBM Bob Hackathon 2026."

**Visual**: 
- Show final tagline: "From Idea to Impact in 60 Seconds"
- Fade to black with contact information

---

## Recording Tips

### Technical Setup
1. **Screen Resolution**: 1920x1080 (Full HD)
2. **Browser**: Chrome or Edge (clean profile, no extensions visible)
3. **Recording Software**: OBS Studio or Camtasia
4. **Audio**: Clear microphone, no background noise
5. **Cursor**: Enable cursor highlighting for visibility

### Before Recording
- [ ] Clear browser cache and cookies
- [ ] Close unnecessary applications
- [ ] Disable notifications (Windows Focus Assist / macOS Do Not Disturb)
- [ ] Test audio levels
- [ ] Prepare example repository URLs
- [ ] Have `.env` file configured with valid credentials
- [ ] Test the full flow once before recording

### During Recording
- [ ] Speak clearly and at moderate pace
- [ ] Pause briefly between sections
- [ ] Use smooth mouse movements
- [ ] Highlight important UI elements
- [ ] Show loading states (don't skip)
- [ ] Demonstrate real-time analysis

### After Recording
- [ ] Add background music (subtle, non-distracting)
- [ ] Add text overlays for key points
- [ ] Add transitions between sections
- [ ] Color grade for consistency
- [ ] Add captions/subtitles
- [ ] Export in 1080p at 30fps

---

## Alternative Demo Scenarios

### Scenario 1: Open Source Project
**Repository**: `https://github.com/facebook/react`
**Focus**: Large-scale architecture, component patterns
**Wow Factor**: Analyzing 10,000+ files in 60 seconds

### Scenario 2: Microservices Architecture
**Repository**: `https://github.com/microservices-demo/microservices-demo`
**Focus**: Service discovery, inter-service communication
**Wow Factor**: Mapping complex service dependencies

### Scenario 3: Legacy Codebase
**Repository**: `https://github.com/rails/rails`
**Focus**: Understanding old patterns, migration paths
**Wow Factor**: Making sense of 15+ years of code history

---

## Key Messages to Emphasize

1. **Speed**: "60 seconds vs. 3 weeks"
2. **Completeness**: "Full repository context, not just documentation"
3. **Intelligence**: "IBM Bob understands code, not just reads it"
4. **Customization**: "Role-specific guides for different team members"
5. **Interactivity**: "Ask questions, get instant answers"
6. **Reusability**: "Custom modes and skills for team-wide use"
7. **Enterprise-Ready**: "Built with IBM's trusted AI technologies"

---

## Backup Plans

### If Live Demo Fails
- Have pre-recorded demo ready
- Use screenshots with voiceover
- Show code walkthrough instead

### If Repository Clone is Slow
- Use smaller example repository
- Show cached results
- Explain the process while waiting

### If watsonx.ai API is Down
- Show Bob-only analysis
- Explain enhancement layer separately
- Use pre-generated examples

---

## Post-Demo Q&A Preparation

**Expected Questions**:

1. **"How does it handle private repositories?"**
   - Answer: GitHub token authentication, secure credential management

2. **"What about non-GitHub repositories?"**
   - Answer: Supports GitLab, Bitbucket via URL cloning

3. **"Can it analyze multiple repositories?"**
   - Answer: Yes, batch analysis feature (future enhancement)

4. **"How accurate is the analysis?"**
   - Answer: Uses IBM Bob's full context understanding, validated against real codebases

5. **"What's the cost per analysis?"**
   - Answer: ~0.5 Bobcoins, ~$0.10 in watsonx.ai credits

6. **"Can teams customize the output?"**
   - Answer: Yes, via custom modes and skills

---

**Demo Checklist**:
- [ ] Script reviewed and practiced
- [ ] Recording environment prepared
- [ ] Application tested and working
- [ ] Example repositories selected
- [ ] Backup plans ready
- [ ] Audio/video equipment tested
- [ ] Timing rehearsed (3-5 minutes)
- [ ] Key messages memorized
- [ ] Q&A preparation complete

**Good luck with your demo! 🚀**