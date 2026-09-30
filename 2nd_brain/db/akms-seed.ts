/**
 * AKMS Sample Data — populate the store with cross-domain knowledge
 * 
 * Covers:
 *   Academic Research, Software Engineering, Electrical Engineering,
 *   AI/ML, Creative, Economics, Project Management, Cybersecurity,
 *   Mechanical Engineering, Business, Mathematics, Physics
 */

import { akms } from './akms-store';
import type { Entity, KnowledgeDomain } from './akms-schema';

// ═══════════════════════════════════════════════
// SEED FUNCTION
// ═══════════════════════════════════════════════

export function seedAKMS(): void {
  if (akms.getAllEntities().length > 0) return; // already seeded

  // ─── PROJECTS ──────────────────────────────

  const robotArm = akms.createEntity('project', 'Robot Arm Control System',
    'Full-stack robot arm project with PCB design, firmware, Python controller, and AI vision',
    'hardware_engineering', { priority: 'high', deadline: '2026-12-01' }, 'active', undefined, 0.9);

  const sensorNetwork = akms.createEntity('project', 'IoT Sensor Network',
    'Distributed sensor network for environmental monitoring with LoRa connectivity',
    'electrical_engineering', { budget: 5000, sensors: 12 }, 'planning', undefined, 0.7);

  const tradingBot = akms.createEntity('project', 'Algorithmic Trading Bot',
    'ML-based trading system with real-time market data and risk management',
    'finance', { capital: 10000, risk_level: 'moderate' }, 'executing', undefined, 0.8);

  const thesisProject = akms.createEntity('project', 'PhD Thesis: Multi-Agent RL',
    'Research project on multi-agent reinforcement learning for robotic coordination',
    'academic_research', { institution: 'MIT', supervisor: 'Dr. Smith' }, 'active', undefined, 0.95);

  // ─── KNOWLEDGE: ELECTRICAL ENGINEERING ─────

  const ohmsLaw = akms.createEntity('law', "Ohm's Law",
    'V = I × R — fundamental relationship between voltage, current, and resistance',
    'electrical_engineering', { formula: 'V = I × R', applies_to: 'linear circuits' }, 'active', undefined, 1.0, 'verified', ['physics', 'circuits']);

  const kirchhoffVoltage = akms.createEntity('law', "Kirchhoff's Voltage Law",
    'Sum of all voltages around a closed loop equals zero',
    'electrical_engineering', { formula: 'ΣV = 0', applies_to: 'closed loops' }, 'active', undefined, 1.0, 'verified', ['circuits']);

  const capacitor = akms.createEntity('concept', 'Capacitor',
    'Passive component that stores energy in electric field. C = Q/V. Reactance Xc = 1/(2πfC)',
    'electrical_engineering', { types: ['ceramic', 'electrolytic', 'tantalum', 'film'], esr_importance: 'high' }, 'active', undefined, 0.95, 'verified', ['components']);

  const voltageRegulator = akms.createEntity('concept', 'Voltage Regulator',
    'Circuit that maintains constant output voltage despite input/load variations. LDO vs switching.',
    'electrical_engineering', { types: ['LDO', 'buck', 'boost', 'buck-boost'], efficiency_range: '60-95%' }, 'active', undefined, 0.9, 'verified', ['power']);

  const mcu = akms.createEntity('concept', 'Microcontroller (MCU)',
    'Integrated circuit with CPU, memory, and peripherals. ARM Cortex-M for embedded.',
    'electrical_engineering', { architectures: ['ARM Cortex-M', 'RISC-V', 'AVR'], flash_kb: '256-2048' }, 'active', undefined, 0.9, 'verified', ['embedded']);

  // ─── KNOWLEDGE: SOFTWARE ENGINEERING ───────

  const restApi = akms.createEntity('concept', 'REST API',
    'Architectural style for web services using HTTP methods. Stateless, resource-based.',
    'software_engineering', { methods: ['GET', 'POST', 'PUT', 'DELETE'], format: 'JSON' }, 'active', undefined, 0.95, 'verified', ['api']);

  const designPattern = akms.createEntity('design_pattern', 'Observer Pattern',
    'Behavioral pattern where objects notify dependents of state changes. Used in event systems.',
    'software_engineering', { gof_category: 'behavioral', uses: ['events', 'reactivity'] }, 'active', undefined, 0.95, 'verified', ['patterns']);

  const cleanArchitecture = akms.createEntity('design_pattern', 'Clean Architecture',
    'Robert Martin\'s architecture with entities, use cases, interfaces, frameworks layers',
    'software_engineering', { layers: ['entities', 'use_cases', 'interfaces', 'frameworks'], dependency_rule: 'inward' }, 'active', undefined, 0.9, 'verified', ['architecture']);

  const gitWorkflow = akms.createEntity('procedure', 'Git Workflow',
    'Branch-based development: feature branches, PR review, CI/CD, merge to main',
    'software_engineering', { branches: ['main', 'develop', 'feature/*'], ci: 'GitHub Actions' }, 'active', undefined, 0.9, 'verified', ['devops']);

  // ─── KNOWLEDGE: AI/ML ─────────────────────

  const transformer = akms.createEntity('concept', 'Transformer Architecture',
    'Self-attention based neural network. Multi-head attention, positional encoding, layer norm.',
    'computer_science_ai', { params: '100B+', attention: 'self-attention', breakthrough: '2017' }, 'active', undefined, 1.0, 'verified', ['dl', 'nlp']);

  const lora = akms.createEntity('method', 'LoRA Fine-tuning',
    'Low-Rank Adaptation for efficient LLM fine-tuning. Freezes base model, trains rank-decomposed matrices.',
    'computer_science_ai', { rank: '4-64', target: ['q_proj', 'v_proj'], trainable_params: '0.1-1%' }, 'active', undefined, 0.95, 'verified', ['llm', 'fine-tuning']);

  const rag = akms.createEntity('method', 'Retrieval-Augmented Generation',
    'Combines retrieval from knowledge base with LLM generation for grounded responses.',
    'computer_science_ai', { components: ['retriever', 'generator', 'knowledge_base'], chunk_size: '512 tokens' }, 'active', undefined, 0.9, 'verified', ['llm', 'agents']);

  const reinforcementLearning = akms.createEntity('concept', 'Reinforcement Learning',
    'Agent learns by interacting with environment, maximizing cumulative reward.',
    'computer_science_ai', { algorithms: ['PPO', 'DQN', 'SAC', 'A3C'], key_concepts: ['policy', 'value', 'reward'] }, 'active', undefined, 0.95, 'verified', ['ml']);

  // ─── KNOWLEDGE: MATHEMATICS ───────────────

  const linearAlgebra = akms.createEntity('concept', 'Linear Algebra',
    'Foundation of ML: vectors, matrices, eigenvalues, SVD, matrix decomposition',
    'mathematics', { key_concepts: ['vectors', 'matrices', 'eigendecomposition', 'SVD'], ml_use: 'weights, embeddings, attention' }, 'active', undefined, 1.0, 'verified', ['ml']);

  const probabilityTheory = akms.createEntity('concept', 'Probability Theory',
    'Mathematical framework for uncertainty. Bayesian inference, distributions, MLE.',
    'mathematics', { key_concepts: ['bayes', 'distributions', 'MLE', 'MAP'], ml_use: 'loss functions, uncertainty' }, 'active', undefined, 1.0, 'verified', ['ml']);

  const optimization = akms.createEntity('concept', 'Optimization Theory',
    'Finding minimum/maximum of functions. Gradient descent, convex optimization.',
    'mathematics', { algorithms: ['GD', 'Adam', 'SGD', 'L-BFGS'], ml_use: 'training' }, 'active', undefined, 0.95, 'verified', ['ml']);

  // ─── KNOWLEDGE: CREATIVE ──────────────────

  const generativeArt = akms.createEntity('method', 'Generative Art',
    'Using algorithms (GANs, diffusion, VAEs) to create images, music, video',
    'creative', { models: ['Stable Diffusion', 'DALL-E', 'Midjourney', 'Suno'], modalities: ['image', 'audio', 'video'] }, 'active', undefined, 0.9, 'verified', ['generative']);

  const colorTheory = akms.createEntity('concept', 'Color Theory',
    'Principles of color mixing, harmony, psychology. RGB/CMYK/HSL color models.',
    'creative', { models: ['RGB', 'CMYK', 'HSL'], harmonies: ['complementary', 'analogous', 'triadic'] }, 'active', undefined, 0.95, 'verified', ['design']);

  // ─── KNOWLEDGE: ECONOMICS/FINANCE ─────────

  const compoundInterest = akms.createEntity('formula', 'Compound Interest',
    'A = P(1 + r/n)^(nt) — foundation of financial growth',
    'finance', { formula: 'A = P(1 + r/n)^(nt)', variables: 'P=principal, r=rate, n=compounds/year, t=years' }, 'active', undefined, 1.0, 'verified', ['finance']);

  const capm = akms.createEntity('formula', 'Capital Asset Pricing Model',
    'Expected return = Rf + β(Rm - Rf). Links risk (beta) to expected return.',
    'finance', { formula: 'E(Ri) = Rf + βi[E(Rm) - Rf]', risk_measure: 'beta' }, 'active', undefined, 0.9, 'verified', ['finance']);

  const monteCarlo = akms.createEntity('method', 'Monte Carlo Simulation',
    'Statistical technique using random sampling to model probability of outcomes',
    'mathematics', { applications: ['risk_analysis', 'option_pricing', 'physics'], iterations: '1000-1000000' }, 'active', undefined, 0.9, 'verified', ['simulation']);

  // ─── KNOWLEDGE: PROJECT MANAGEMENT ────────

  const wbs = akms.createEntity('method', 'Work Breakdown Structure',
    'Hierarchical decomposition of project scope into manageable work packages',
    'project_management', { levels: ['project', 'phase', 'deliverable', 'work_package'] }, 'active', undefined, 0.95, 'verified', ['planning']);

  const agileMethodology = akms.createEntity('procedure', 'Agile/Scrum Methodology',
    'Iterative development with sprints, daily standups, retrospectives',
    'project_management', { ceremonies: ['sprint_planning', 'daily_standup', 'review', 'retro'], sprint_length: '2 weeks' }, 'active', undefined, 0.9, 'verified', ['agile']);

  // ─── KNOWLEDGE: CYBERSECURITY ─────────────

  const principleOfLeastPrivilege = akms.createEntity('principle', 'Principle of Least Privilege',
    'Entities should have minimum permissions necessary for their function',
    'cybersecurity', { applies_to: ['users', 'processes', 'services'] }, 'active', undefined, 1.0, 'verified', ['security']);

  const encryption = akms.createEntity('concept', 'Encryption',
    'AES-256 for symmetric, RSA/ECC for asymmetric. Protects data at rest and in transit.',
    'cybersecurity', { symmetric: ['AES-256', 'ChaCha20'], asymmetric: ['RSA-4096', 'ECC'], hashing: ['SHA-256', 'Argon2'] }, 'active', undefined, 0.95, 'verified', ['crypto']);

  // ─── KNOWLEDGE: PHYSICS ───────────────────

  const thermodynamics = akms.createEntity('law', 'Thermodynamics Laws',
    '1st: Energy conserved. 2nd: Entropy increases. 3rd: T→0, S→0.',
    'physics', { laws: ['energy_conservation', 'entropy_increase', 'absolute_zero'], applications: ['heat_transfer', 'engines'] }, 'active', undefined, 1.0, 'verified', ['physics']);

  const fourierTransform = akms.createEntity('formula', 'Fourier Transform',
    'Decomposes signals into frequency components. F(ω) = ∫f(t)e^(-iωt)dt',
    'mathematics', { formula: 'F(ω) = ∫f(t)e^(-iωt)dt', applications: ['signal_processing', 'image_processing', 'quantum'] }, 'active', undefined, 1.0, 'verified', ['signal']);

  // ─── KNOWLEDGE: CHEMISTRY ─────────────────

  const periodicTable = akms.createEntity('concept', 'Periodic Table',
    'Organized by atomic number, groups, periods. Properties periodic with atomic number.',
    'chemistry_materials', { total_elements: 118, groups: 18, periods: 7 }, 'active', undefined, 1.0, 'verified', ['chemistry']);

  // ─── KNOWLEDGE: MECHANICAL ENGINEERING ────

  const stressStrain = akms.createEntity('concept', 'Stress-Strain Relationship',
    'σ = Eε (Hooke\'s law). Young\'s modulus E = σ/ε. Yield strength, ultimate strength.',
    'mechanical_engineering', { formula: 'σ = Eε', key_properties: ['yield_strength', 'ultimate_strength', 'elongation'] }, 'active', undefined, 0.95, 'verified', ['mechanics']);

  const cad = akms.createEntity('tool', 'CAD Software',
    'Computer-Aided Design for 3D modeling. SolidWorks, Fusion 360, FreeCAD.',
    'mechanical_engineering', { software: ['SolidWorks', 'Fusion 360', 'FreeCAD'], file_formats: ['STEP', 'STL', 'IGES'] }, 'active', undefined, 0.9, 'verified', ['design']);

  // ─── KNOWLEDGE: CIVIL ENGINEERING ─────────

  const beamAnalysis = akms.createEntity('concept', 'Beam Analysis',
    'Structural element resisting load. Simply supported, cantilever, fixed. Bending moment, shear.',
    'civil_engineering', { beam_types: ['simply_supported', 'cantilever', 'fixed', 'continuous'], loads: ['point', 'distributed', 'moment'] }, 'active', undefined, 0.9, 'verified', ['structures']);

  // ─── KNOWLEDGE: CONTROL SYSTEMS ───────────

  const pidController = akms.createEntity('concept', 'PID Controller',
    'Proportional-Integral-Derivative controller for feedback systems',
    'control_automation', { formula: 'u(t) = Kp*e(t) + Ki*∫e(t)dt + Kd*de/dt', applications: ['motor_control', 'temperature', 'robotics'] }, 'active', undefined, 0.95, 'verified', ['control']);

  const transferFunction = akms.createEntity('concept', 'Transfer Function',
    'Laplace transform ratio of output to input: G(s) = Y(s)/U(s)',
    'control_automation', { domain: 'Laplace', analysis: ['pole_zero', 'bode', 'nyquist'] }, 'active', undefined, 0.9, 'verified', ['control']);

  // ─── KNOWLEDGE: BUSINESS ──────────────────

  const swotAnalysis = akms.createEntity('method', 'SWOT Analysis',
    'Strengths, Weaknesses, Opportunities, Threats — strategic planning framework',
    'business', { quadrants: ['strengths', 'weaknesses', 'opportunities', 'threats'] }, 'active', undefined, 0.9, 'verified', ['strategy']);

  const businessModelCanvas = akms.createEntity('method', 'Business Model Canvas',
    'Alexander Osterwalder\'s 9-building-block framework for business models',
    'business', { blocks: ['value_prop', 'customer_segments', 'channels', 'revenue_streams', 'key_resources', 'key_activities', 'partnerships', 'cost_structure', 'customer_relationships'] }, 'active', undefined, 0.9, 'verified', ['strategy']);

  // ─── KNOWLEDGE: LEGAL ─────────────────────

  const intellectualProperty = akms.createEntity('concept', 'Intellectual Property',
    'Patents, copyrights, trademarks, trade secrets. Protects inventions and creative works.',
    'legal_compliance', { types: ['patent', 'copyright', 'trademark', 'trade_secret'], duration: '20 years (patent), life+70 (copyright)' }, 'active', undefined, 0.9, 'verified', ['ip']);

  // ─── KNOWLEDGE: DATA SCIENCE ──────────────

  const pandas = akms.createEntity('tool', 'Pandas (Python)',
    'Data manipulation library. DataFrame, Series, groupby, merge, pivot.',
    'data_science', { version: '2.x', key_features: ['DataFrame', 'Series', 'groupby', 'merge', 'pivot_table'] }, 'active', undefined, 0.95, 'verified', ['python']);

  const scikitLearn = akms.createEntity('tool', 'Scikit-Learn',
    'ML library for classification, regression, clustering, dimensionality reduction.',
    'data_science', { algorithms: ['SVM', 'Random Forest', 'Gradient Boosting', 'KNN', 'K-Means'], api: 'fit/predict/transform' }, 'active', undefined, 0.95, 'verified', ['ml']);

  // ─── EXPERIENCES (MEMORY) ─────────────────

  akms.createEntity('experience', 'PCB Capacitor Lesson',
    'Changed C17 on sensor PCB regulator — wrong ESR caused voltage instability. Lesson: always check capacitor ESR range for regulator configs.',
    'electrical_engineering', { lesson: 'check ESR range', component: 'C17', failure_mode: 'voltage instability' }, 'completed', 'experience', 0.97, 'verified', ['pcb', 'capacitor']);

  akms.createEntity('failure', 'PCB Attempt #4 Failed',
    'Changed capacitor C17 to wrong spec. Voltage became unstable. Root cause: wrong ESR.',
    'electrical_engineering', { component: 'C17', error: 'wrong ESR', symptom: 'voltage instability' }, 'completed', 'failure', 0.95, 'verified', ['pcb', 'failure']);

  akms.createEntity('lesson', 'Capacitor ESR Rule',
    'For linear regulators, always verify capacitor ESR is within datasheet range. Ceramic caps often have too-low ESR for older LDOs.',
    'electrical_engineering', { rule: 'verify ESR range', applies_to: 'LDO circuits', source: 'datasheet + experiment' }, 'active', 'lesson', 0.98, 'verified', ['rule', 'pcb']);

  akms.createEntity('decision', 'Use ARM Cortex-M for Robot Arm',
    'Chose STM32F4 over ESP32 for robot arm MCU due to better ADC, PWM resolution, and real-time performance.',
    'hardware_engineering', { chosen: 'STM32F4', rejected: ['ESP32', 'Arduino Mega'], reasons: ['ADC精度', 'PWM分辨率', 'real-time'] }, 'completed', 'decision', 0.9, 'verified', ['mcu', 'robot']);

  akms.createEntity('experience', 'Transformer Architecture Works',
    'Successfully implemented GPT-2 style model. Self-attention captures long-range dependencies better than RNN/LSTM.',
    'computer_science_ai', { model: 'GPT-2', finding: 'self-attention superior to RNN' }, 'completed', 'experience', 0.95, 'verified', ['transformer', 'dl']);

  akms.createEntity('failure', 'RNN Vanishing Gradient',
    'Vanilla RNN failed to learn long sequences (>100 steps). Gradient vanished below 1e-6.',
    'computer_science_ai', { model: 'Vanilla RNN', failure: 'vanishing_gradient', max_sequence: 100 }, 'completed', 'failure', 0.95, 'verified', ['rnn', 'failure']);

  akms.createEntity('lesson', 'Use Gradient Clipping',
    'Always use gradient clipping (max_norm=1.0) for RNN training. Prevents exploding gradients.',
    'computer_science_ai', { rule: 'clip gradients', max_norm: 1.0, applies_to: 'RNN/LSTM' }, 'active', 'lesson', 0.95, 'verified', ['training', 'rule']);

  akms.createEntity('session', 'Morning Coding Session',
    'Worked on robot arm IK solver. Implemented Jacobian-based method. Testing with simulation.',
    'software_engineering', { duration: '3 hours', tasks: ['IK solver', 'Jacobian', 'simulation'] }, 'completed', 'session', 0.8, 'unverified', ['coding']);

  akms.createEntity('observation', 'VS Code Extension Patterns',
    'Most popular VS Code extensions use webview panels, language server protocol, and tree views.',
    'software_engineering', { patterns: ['webview', 'LSP', 'tree_view'], observation_date: '2026-09' }, 'active', 'observation', 0.85, 'sourced', ['vscode']);

  akms.createEntity('decision', 'Use TypeScript for IGRIS',
    'Decided TypeScript over JavaScript for type safety, better DX, and easier maintenance.',
    'software_engineering', { chosen: 'TypeScript', rejected: ['JavaScript', 'ReasonML'], reasons: ['type_safety', 'DX', 'maintenance'] }, 'completed', 'decision', 0.9, 'verified', ['typescript']);

  // ─── EVIDENCE for key claims ──────────────

  const ohmsLawEntity = akms.findEntities({ type: 'law' })[0];
  if (ohmsLawEntity) {
    akms.addEvidence(ohmsLawEntity.id, 'textbook',
      'Fundamentals of Electric Circuits, Alexander & Sadiku, Chapter 2',
      "Ohm's Law V = IR is universally valid for linear resistive elements at constant temperature",
      'Verified through 100+ years of experimental validation', '', undefined, 1.0);
  }

  const transformerEntity = akms.findEntities({ type: 'concept' }).find(e => e.name.includes('Transformer'));
  if (transformerEntity) {
    akms.addEvidence(transformerEntity.id, 'paper',
      'Attention Is All You Need, Vaswani et al., NeurIPS 2017',
      'Transformer with self-attention achieves state-of-the-art on machine translation',
      'Cited 100,000+ times, foundation of GPT/BERT/etc.', '', undefined, 1.0);
  }

  const loraEntity = akms.findEntities({ type: 'method' }).find(e => e.name.includes('LoRA'));
  if (loraEntity) {
    akms.addEvidence(loraEntity.id, 'paper',
      'LoRA: Low-Rank Adaptation of Large Language Models, Hu et al., ICLR 2022',
      'LoRA matches full fine-tuning performance while training <1% parameters',
      'Validated on GPT-3 175B, RoBERTa, DeBERTa', '', undefined, 0.95);
  }

  // ─── RELATIONS between knowledge ──────────

  const allEntities = akms.getAllEntities();
  const findBy = (name: string) => allEntities.find(e => e.name.includes(name));

  // Electrical Engineering relations
  const oe = findBy("Ohm's Law");
  const kv = findBy("Kirchhoff");
  const cap = findBy("Capacitor");
  const reg = findBy("Voltage Regulator");
  const mcuE = findBy("Microcontroller");
  if (oe && kv) akms.addRelation(oe.id, kv.id, 'extends', 0.9);
  if (cap && reg) akms.addRelation(cap.id, reg.id, 'used_in', 0.9);
  if (reg && mcuE) akms.addRelation(reg.id, mcuE.id, 'used_in', 0.8);
  if (cap && mcuE) akms.addRelation(cap.id, mcuE.id, 'used_in', 0.8);

  // Software Engineering relations
  const rest = findBy("REST API");
  const obs = findBy("Observer");
  const clean = findBy("Clean Architecture");
  const git = findBy("Git Workflow");
  if (rest && clean) akms.addRelation(rest.id, clean.id, 'implements', 0.8);
  if (obs && clean) akms.addRelation(obs.id, clean.id, 'used_in', 0.7);
  if (git && clean) akms.addRelation(git.id, clean.id, 'supports', 0.6);

  // AI/ML relations
  const trans = findBy("Transformer");
  const loraE = findBy("LoRA");
  const ragE = findBy("Retrieval-Augmented");
  const rl = findBy("Reinforcement Learning");
  const linAlg = findBy("Linear Algebra");
  const prob = findBy("Probability");
  const opt = findBy("Optimization");
  if (trans && loraE) akms.addRelation(loraE.id, trans.id, 'extends', 0.9);
  if (trans && ragE) akms.addRelation(ragE.id, trans.id, 'uses', 0.8);
  if (linAlg && trans) akms.addRelation(trans.id, linAlg.id, 'depends_on', 0.95);
  if (prob && trans) akms.addRelation(trans.id, prob.id, 'depends_on', 0.9);
  if (opt && trans) akms.addRelation(trans.id, opt.id, 'depends_on', 0.9);
  if (rl && trans) akms.addRelation(rl.id, trans.id, 'uses', 0.7);

  // Finance relations
  const comp = findBy("Compound Interest");
  const capmE = findBy("Capital Asset");
  const mc = findBy("Monte Carlo");
  if (comp && capmE) akms.addRelation(capmE.id, comp.id, 'extends', 0.7);
  if (mc && capmE) akms.addRelation(mc.id, capmE.id, 'uses', 0.8);
  if (prob && mc) akms.addRelation(mc.id, prob.id, 'depends_on', 0.9);

  // Project Management relations
  const wbsE = findBy("Work Breakdown");
  const agile = findBy("Agile");
  const pmProject = findBy("Robot Arm Control");
  if (wbsE && agile) akms.addRelation(wbsE.id, agile.id, 'used_in', 0.8);
  if (wbsE && pmProject) akms.addRelation(pmProject.id, wbsE.id, 'uses', 0.9);
  if (agile && pmProject) akms.addRelation(pmProject.id, agile.id, 'uses', 0.9);

  // Cross-domain relations
  if (mcuE && robotArm) akms.addRelation(mcuE.id, robotArm.id, 'used_in', 0.9);
  const pidE = findBy("PID");
  if (pidE) akms.addRelation(pidE.id, robotArm.id, 'used_in', 0.85);
  const stressE = findBy("Stress-Strain");
  if (stressE && sensorNetwork) akms.addRelation(stressE.id, sensorNetwork.id, 'used_in', 0.6);
  if (trans && thesisProject) akms.addRelation(trans.id, thesisProject.id, 'used_in', 0.95);
  if (rl && thesisProject) akms.addRelation(rl.id, thesisProject.id, 'used_in', 0.95);
  const linAlgE = findBy("Linear Algebra");
  if (linAlgE && tradingBot) akms.addRelation(linAlgE.id, tradingBot.id, 'used_in', 0.7);
  if (mc && tradingBot) akms.addRelation(mc.id, tradingBot.id, 'used_in', 0.85);
  if (loraE && tradingBot) akms.addRelation(loraE.id, tradingBot.id, 'used_in', 0.7);

  // Creative relations
  const genArt = findBy("Generative Art");
  const color = findBy("Color Theory");
  if (genArt && color) akms.addRelation(genArt.id, color.id, 'depends_on', 0.8);

  // Security relations
  const polp = findBy("Principle of Least");
  const enc = findBy("Encryption");
  if (polp && enc) akms.addRelation(enc.id, polp.id, 'implements', 0.9);

  // Lessons learned relations
  const failCap = findBy("PCB Attempt #4");
  const expCap = findBy("PCB Capacitor Lesson");
  const lessonCap = findBy("Capacitor ESR Rule");
  if (failCap && expCap) akms.addRelation(expCap.id, failCap.id, 'learned_from', 1.0);
  if (expCap && lessonCap) akms.addRelation(lessonCap.id, expCap.id, 'derived_from', 0.95);
  const capE = findBy("Capacitor");
  if (lessonCap && capE) akms.addRelation(lessonCap.id, capE.id, 'relates_to', 0.9);
  const vregE = findBy("Voltage Regulator");
  if (lessonCap && vregE) akms.addRelation(lessonCap.id, vregE.id, 'relates_to', 0.9);

  // Verification relations
  const ohmsEntity = findBy("Ohm's Law");
  if (ohmsEntity) {
    const evs = akms.getEvidenceFor(ohmsEntity.id);
    if (evs.length > 0) {
      akms.addRelation(ohmsEntity.id, evs[0].id, 'verified_by', 1.0);
    }
  }
}

// ═══════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════

export function getAKMSStats() {
  return akms.getStats();
}
