# Onboarding Guide Generator Skill

## Purpose
Generate comprehensive onboarding guides for any codebase, reducing new developer ramp-up time from weeks to minutes.

## When to Use
- New team member joining
- Analyzing unfamiliar codebase
- Creating documentation for existing projects
- Preparing for code reviews or audits
- Understanding legacy systems

## How to Use
1. Ensure you have access to the full repository
2. Switch to "Onboarding Guide Generator" mode
3. Provide the repository path or GitHub URL
4. Specify the target role (Engineer/Manager/Architect)
5. Review and customize the generated guide

## Expected Output
- Structured markdown document
- Architecture diagrams (Mermaid)
- Role-specific insights
- Actionable next steps
- Interactive Q&A capability

## Example Usage

### Basic Analysis
```
@mode onboarding-guide-generator
Analyze this repository and create an onboarding guide for a new backend engineer.
Repository: /path/to/repo
```

### Role-Specific Analysis
```
@mode onboarding-guide-generator
Create an onboarding guide for an Engineering Manager.
Focus on: tech stack overview, team structure, risk areas, resource requirements.
Repository: /path/to/repo
```

### Focused Analysis
```
@mode onboarding-guide-generator
Analyze the authentication module and create a focused onboarding guide.
Target: @folder src/auth
Role: Senior Engineer
```

## Tips for Best Results
- For large repos, focus on core modules first using @folder mentions
- Use @file mentions to analyze specific critical files
- Generate multiple role-specific views for comprehensive coverage
- Export as HTML for better presentation
- Save as a reusable template for similar projects

## Output Sections

The generated guide includes:

1. **Project Overview** - What the project does, tech stack summary
2. **Architecture & Design** - System architecture, design patterns, data flow
3. **Key Components** - Critical files, directory structure, entry points
4. **Setup & Installation** - Prerequisites, installation steps, verification
5. **Development Workflow** - Running locally, building, testing, code quality
6. **Testing Strategy** - Test structure, running tests, coverage
7. **First Contribution Guide** - Reading order, good first issues, first PR steps
8. **Role-Specific Insights** - Tailored content for Engineers/Managers/Architects
9. **Visual Diagrams** - Architecture diagrams, data flow, component relationships

## Integration with SmartOnboard

This skill is the core of the SmartOnboard application:

1. User provides GitHub URL
2. Repository is cloned locally
3. This skill analyzes the codebase
4. watsonx.ai enhances the output
5. Beautiful HTML guide is generated
6. Interactive Q&A becomes available

## Customization

You can customize the analysis by:

- Specifying focus areas: "Focus on the API layer"
- Requesting specific diagrams: "Include sequence diagrams for authentication"
- Adjusting depth: "Provide a high-level overview" or "Deep technical analysis"
- Adding constraints: "Assume the reader knows React but not TypeScript"

## Quality Checklist

Before delivering the guide, ensure:

- [ ] All critical files are identified and explained
- [ ] Setup instructions are complete and tested
- [ ] Architecture diagrams are clear and accurate
- [ ] Code examples are included where helpful
- [ ] Role-specific content is appropriately tailored
- [ ] First contribution guide provides clear next steps
- [ ] Technical terms are explained or linked
- [ ] Common pitfalls are documented

## Maintenance

To keep guides up-to-date:

- Re-run analysis when major changes occur
- Update setup instructions when dependencies change
- Refresh architecture diagrams after refactoring
- Add new patterns as they emerge
- Document breaking changes

## Advanced Usage

### Multi-Repository Analysis
```
@mode onboarding-guide-generator
Analyze these microservices and create a unified onboarding guide:
- @folder ../service-auth
- @folder ../service-api
- @folder ../service-data
```

### Comparative Analysis
```
@mode onboarding-guide-generator
Compare the architecture of this project with standard patterns.
Highlight deviations and explain why they might exist.
```

### Migration Guide
```
@mode onboarding-guide-generator
Create a guide for developers migrating from the old system.
Focus on: architectural differences, new patterns, migration path.
```

## Success Metrics

A successful onboarding guide should:

- Reduce time-to-first-contribution by 80%+
- Answer 90% of common questions
- Be readable in under 30 minutes
- Provide clear next steps
- Include working code examples
- Have up-to-date setup instructions

## Support

For issues or questions:
- Check the SmartOnboard documentation
- Review example guides in the repository
- Ask in the team chat
- Submit feedback for improvements

---

**Version**: 1.0.0  
**Last Updated**: 2026-05-15  
**Maintained by**: SmartOnboard Team