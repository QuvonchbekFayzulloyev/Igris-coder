/**
 * PCM Sample Data — comprehensive professions with full capability maps
 * 
 * Covers: Electrical Engineering, Software Engineering, Data Science,
 * Economics, Project Management, Creative, Academic Research, AI/ML
 */

import { pcm } from './pcm-store';
import type { KnowledgeDomain } from './akms-schema';

// ═══════════════════════════════════════════════
// SEED FUNCTION
// ═══════════════════════════════════════════════

export function seedPCM(): void {
  if (pcm.getAllProfessions().length > 0) return;

  // ─── SHARED SKILLS ────────────────────────

  const pythonSkill = pcm.createSkill('Python', 'Python programming language', 'computer_science_ai', 'advanced');
  const statsSkill = pcm.createSkill('Statistics', 'Statistical analysis and inference', 'data_science', 'advanced');
  const cadSkill = pcm.createSkill('3D CAD Modeling', 'Computer-aided 3D design', 'mechanical_engineering', 'advanced');
  const schematicSkill = pcm.createSkill('Schematic Design', 'Electronic circuit schematics', 'electrical_engineering', 'advanced');
  const projectPlanningSkill = pcm.createSkill('Project Planning', 'WBS, scheduling, resource allocation', 'project_management', 'advanced');
  const researchSkill = pcm.createSkill('Research Methodology', 'Scientific research methods', 'academic_research', 'expert');
  const writingSkill = pcm.createSkill('Technical Writing', 'Clear technical documentation', 'general', 'advanced');
  const dataCleaning = pcm.createSkill('Data Cleaning', 'Preparing data for analysis', 'data_science', 'advanced');
  const versionControl = pcm.createSkill('Version Control', 'Git, branching, PR workflows', 'software_engineering', 'advanced');
  const testingSkill = pcm.createSkill('Testing', 'Unit, integration, system testing', 'software_engineering', 'advanced');

  // ─── SHARED TOOLS ─────────────────────────

  const kicadTool = pcm.createTool('KiCad', 'Open-source EDA suite', 'eda', ['linux', 'windows', 'mac']);
  const altiumTool = pcm.createTool('Altium Designer', 'Professional PCB design', 'eda', ['windows']);
  const solidworksTool = pcm.createTool('SolidWorks', '3D CAD software', 'cad', ['windows']);
  const fusionTool = pcm.createTool('Fusion 360', 'Cloud-based CAD/CAM', 'cad', ['windows', 'mac']);
  const matlabTool = pcm.createTool('MATLAB', 'Numerical computing', 'simulation', ['windows', 'linux', 'mac']);
  const pythonTool = pcm.createTool('Python', 'Programming language', 'ide', ['windows', 'linux', 'mac']);
  const jupyterTool = pcm.createTool('Jupyter Notebook', 'Interactive computing', 'ide', ['windows', 'linux', 'mac']);
  const excelTool = pcm.createTool('Microsoft Excel', 'Spreadsheet software', 'office', ['windows', 'mac']);
  const wordTool = pcm.createTool('Microsoft Word', 'Word processor', 'office', ['windows', 'mac']);
  const pptTool = pcm.createTool('Microsoft PowerPoint', 'Presentation software', 'office', ['windows', 'mac']);
  const vscodeTool = pcm.createTool('VS Code', 'Code editor', 'ide', ['windows', 'linux', 'mac']);
  const gitTool = pcm.createTool('Git', 'Version control system', 'vcs', ['windows', 'linux', 'mac']);

  // ─── SHARED KNOWLEDGE ─────────────────────

  const linearAlg = pcm.createKnowledge('Linear Algebra', 'Vectors, matrices, eigenvalues', 'mathematics', 'concept', 'advanced');
  const probability = pcm.createKnowledge('Probability Theory', 'Probability, statistics, distributions', 'mathematics', 'concept', 'advanced');
  const signalTheory = pcm.createKnowledge('Signal Processing', 'FFT, filtering, sampling', 'electrical_engineering', 'concept', 'advanced');
  const controlTheory = pcm.createKnowledge('Control Theory', 'PID, state-space, stability', 'control_automation', 'concept', 'advanced');
  const softwareArch = pcm.createKnowledge('Software Architecture', 'Design patterns, clean architecture', 'software_engineering', 'concept', 'advanced');
  const databases = pcm.createKnowledge('Database Systems', 'SQL, NoSQL, data modeling', 'software_engineering', 'concept', 'advanced');
  const econometrics = pcm.createKnowledge('Econometrics', 'Regression, time series, causality', 'economics', 'concept', 'expert');
  const mlKnowledge = pcm.createKnowledge('Machine Learning', 'Supervised, unsupervised, RL', 'computer_science_ai', 'concept', 'expert');
  const deepLearning = pcm.createKnowledge('Deep Learning', 'Neural networks, transformers', 'computer_science_ai', 'concept', 'expert');
  const projectManagement = pcm.createKnowledge('Project Management', 'WBS, Gantt, Agile, Scrum', 'project_management', 'concept', 'advanced');

  // ═══════════════════════════════════════════
  // PROFESSION 1: ELECTRICAL ENGINEER
  // ═══════════════════════════════════════════

  const eeProf = pcm.createProfession(
    'Electrical Engineer',
    'Design, analyze, and test electronic systems',
    'electrical_engineering',
    '⚡', '#f59e0b'
  );

  // Specialization: Circuit Design
  const eeCircuitSpec = pcm.createSpecialization(
    'Circuit Design',
    'Design and analyze electronic circuits',
    eeProf.id
  );

  const circuitDesignComp = pcm.createCompetency(
    'Circuit Analysis & Design',
    'Design analog and digital circuits',
    'electrical_engineering',
    [eeProf.id]
  );
  eeCircuitSpec.competencies.push(circuitDesignComp.id);

  // Tasks for Circuit Design
  const schematicTask = pcm.createTask(
    'Schematic Design',
    'Create circuit schematics from requirements',
    'electrical_engineering', 'complex', circuitDesignComp.id
  );
  schematicTask.requiredKnowledge = [signalTheory.id, controlTheory.id];
  schematicTask.requiredSkills = [schematicSkill.id];
  schematicTask.requiredTools = [kicadTool.id, altiumTool.id];
  schematicTask.inputs = [
    { id: uid(), name: 'Requirements', type: 'parameter', description: 'Circuit requirements', required: true },
    { id: uid(), name: 'Components', type: 'data', description: 'Available components', required: true },
  ];
  schematicTask.outputs = [
    { id: uid(), name: 'Schematic', type: 'file', format: 'kicad_sch', description: 'Circuit schematic', required: true },
    { id: uid(), name: 'BOM', type: 'file', format: 'csv', description: 'Bill of materials', required: true },
  ];
  schematicTask.workflow = [
    { id: uid(), order: 1, name: 'Analyze requirements', action: 'Parse and understand circuit requirements', requiredKnowledge: [], requiredSkills: [], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Select topology', action: 'Choose circuit topology', requiredKnowledge: [signalTheory.id], requiredSkills: [schematicSkill.id], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Select components', action: 'Choose specific components', requiredKnowledge: [], requiredSkills: [], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Draw schematic', action: 'Create schematic in EDA tool', requiredKnowledge: [], requiredSkills: [schematicSkill.id], requiredTools: [kicadTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Run simulation', action: 'Simulate circuit', requiredKnowledge: [], requiredSkills: [], requiredTools: [matlabTool.id], inputs: [], outputs: [], verification: [] },
  ];
  schematicTask.verification = [
    { id: uid(), name: 'ERC', method: 'testing', description: 'Electrical Rule Check', checkType: 'erc', expectedResults: ['No violations'], onFail: 'retry' },
    { id: uid(), name: 'Simulation', method: 'simulation', description: 'Circuit simulation', checkType: 'simulation', expectedResults: ['Within specs'], onFail: 'retry' },
  ];
  schematicTask.constraints = [
    { id: uid(), type: 'technical', name: 'Voltage range', description: 'Operating voltage', metric: 'voltage', limit: '3.3V-5V', hard: true },
    { id: uid(), type: 'financial', name: 'BOM cost', description: 'Bill of materials cost', metric: 'cost', limit: '$50', hard: false },
  ];
  schematicTask.failureModes = [
    { id: uid(), name: 'Component unavailability', description: 'Selected component not available', cause: 'Supply chain issue', symptom: 'Cannot source parts', severity: 'medium', probability: 'possible', detectionMethod: 'BOM check', prevention: ['Use multiple suppliers', 'Design for substitution'], mitigation: ['Alternative components', 'Redesign'], occurredBefore: false },
  ];

  // Specialization: PCB Engineering
  const eePCBSpec = pcm.createSpecialization(
    'PCB Engineering',
    'Design and layout printed circuit boards',
    eeProf.id
  );

  const pcbDesignComp = pcm.createCompetency(
    'PCB Design & Layout',
    'Design PCB stackup, placement, routing',
    'electrical_engineering',
    [eeProf.id]
  );
  eePCBSpec.competencies.push(pcbDesignComp.id);

  const pcbLayoutTask = pcm.createTask(
    'PCB Layout',
    'Create PCB layout from schematic',
    'electrical_engineering', 'complex', pcbDesignComp.id
  );
  pcbLayoutTask.requiredKnowledge = [signalTheory.id];
  pcbLayoutTask.requiredSkills = [schematicSkill.id];
  pcbLayoutTask.requiredTools = [kicadTool.id, altiumTool.id];
  pcbLayoutTask.inputs = [
    { id: uid(), name: 'Schematic', type: 'file', format: 'kicad_sch', description: 'Circuit schematic', required: true },
    { id: uid(), name: 'Board dimensions', type: 'parameter', description: 'Physical constraints', required: true },
  ];
  pcbLayoutTask.outputs = [
    { id: uid(), name: 'PCB Layout', type: 'file', format: 'kicad_pcb', description: 'PCB layout file', required: true },
    { id: uid(), name: 'Gerber files', type: 'file', format: 'gerber', description: 'Manufacturing files', required: true },
  ];
  pcbLayoutTask.workflow = [
    { id: uid(), order: 1, name: 'Define stackup', action: 'Define PCB layer stackup', requiredKnowledge: [], requiredSkills: [], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Import netlist', action: 'Import schematic netlist', requiredKnowledge: [], requiredSkills: [schematicSkill.id], requiredTools: [kicadTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Place components', action: 'Place components on board', requiredKnowledge: [], requiredSkills: [], requiredTools: [kicadTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Route traces', action: 'Route signal and power traces', requiredKnowledge: [signalTheory.id], requiredSkills: [], requiredTools: [kicadTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Run DRC', action: 'Design Rule Check', requiredKnowledge: [], requiredSkills: [], requiredTools: [kicadTool.id], inputs: [], outputs: [], verification: [] },
  ];
  pcbLayoutTask.verification = [
    { id: uid(), name: 'DRC', method: 'testing', description: 'Design Rule Check', checkType: 'drc', expectedResults: ['No violations'], onFail: 'retry' },
    { id: uid(), name: 'Signal Integrity', method: 'simulation', description: 'Signal integrity analysis', checkType: 'simulation', expectedResults: ['Eye diagram open'], onFail: 'retry' },
  ];
  pcbLayoutTask.failureModes = [
    { id: uid(), name: 'Clearance violation', description: 'Insufficient clearance between traces', cause: 'Routing too close', symptom: 'DRC error', severity: 'high', probability: 'likely', detectionMethod: 'DRC', prevention: ['Follow design rules'], mitigation: ['Reroute', 'Increase board size'], occurredBefore: true },
    { id: uid(), name: 'Impedance mismatch', description: 'Trace impedance not matching target', cause: 'Wrong stackup or trace width', symptom: 'Signal reflections', severity: 'high', probability: 'possible', detectionMethod: 'Simulation', prevention: ['Calculate impedance upfront'], mitigation: ['Adjust stackup', 'Change trace width'], occurredBefore: false },
  ];

  // ═══════════════════════════════════════════
  // PROFESSION 2: SOFTWARE ENGINEER
  // ═══════════════════════════════════════════

  const seProf = pcm.createProfession(
    'Software Engineer',
    'Design, develop, and maintain software systems',
    'software_engineering',
    '💻', '#10b981'
  );

  const seFullStackSpec = pcm.createSpecialization(
    'Full-Stack Development',
    'Frontend and backend development',
    seProf.id
  );

  const webDevComp = pcm.createCompetency(
    'Web Application Development',
    'Build web applications with modern frameworks',
    'software_engineering',
    [seProf.id]
  );
  seFullStackSpec.competencies.push(webDevComp.id);

  const apiDesignTask = pcm.createTask(
    'REST API Design',
    'Design and implement RESTful APIs',
    'software_engineering', 'moderate', webDevComp.id
  );
  apiDesignTask.requiredKnowledge = [softwareArch.id, databases.id];
  apiDesignTask.requiredSkills = [pythonSkill.id, versionControl.id];
  apiDesignTask.requiredTools = [vscodeTool.id, gitTool.id];
  apiDesignTask.inputs = [
    { id: uid(), name: 'API Spec', type: 'parameter', description: 'API requirements', required: true },
    { id: uid(), name: 'Database Schema', type: 'data', description: 'Data model', required: true },
  ];
  apiDesignTask.outputs = [
    { id: uid(), name: 'API Code', type: 'file', format: 'python', description: 'API implementation', required: true },
    { id: uid(), name: 'API Docs', type: 'file', format: 'openapi', description: 'OpenAPI specification', required: true },
  ];
  apiDesignTask.workflow = [
    { id: uid(), order: 1, name: 'Define endpoints', action: 'Define API endpoints and methods', requiredKnowledge: [softwareArch.id], requiredSkills: [], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Design data model', action: 'Create database schema', requiredKnowledge: [databases.id], requiredSkills: [], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Implement endpoints', action: 'Write API code', requiredKnowledge: [], requiredSkills: [pythonSkill.id], requiredTools: [vscodeTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Write tests', action: 'Create unit and integration tests', requiredKnowledge: [], requiredSkills: [testingSkill.id], requiredTools: [vscodeTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Document API', action: 'Create OpenAPI documentation', requiredKnowledge: [], requiredSkills: [writingSkill.id], requiredTools: [], inputs: [], outputs: [], verification: [] },
  ];
  apiDesignTask.verification = [
    { id: uid(), name: 'Unit Tests', method: 'testing', description: 'Run unit tests', checkType: 'test', expectedResults: ['All tests pass'], onFail: 'retry' },
    { id: uid(), name: 'Integration Tests', method: 'testing', description: 'Run integration tests', checkType: 'test', expectedResults: ['All endpoints work'], onFail: 'retry' },
  ];
  apiDesignTask.failureModes = [
    { id: uid(), name: 'SQL Injection', description: 'Vulnerability to SQL injection attacks', cause: 'Unsanitized input', symptom: 'Security breach', severity: 'critical', probability: 'possible', detectionMethod: 'Security audit', prevention: ['Use parameterized queries', 'Input validation'], mitigation: ['Patch vulnerability', 'Security audit'], occurredBefore: false },
  ];

  // ═══════════════════════════════════════════
  // PROFESSION 3: DATA SCIENTIST
  // ═══════════════════════════════════════════

  const dsProf = pcm.createProfession(
    'Data Scientist',
    'Extract insights from data using statistical and ML methods',
    'data_science',
    '📊', '#0ea5e9'
  );

  const mlSpec = pcm.createSpecialization(
    'Machine Learning Engineering',
    'Build and deploy ML models',
    dsProf.id
  );

  const mlComp = pcm.createCompetency(
    'ML Model Development',
    'Develop, train, and evaluate ML models',
    'computer_science_ai',
    [dsProf.id]
  );
  mlSpec.competencies.push(mlComp.id);

  const mlTrainingTask = pcm.createTask(
    'ML Model Training',
    'Train machine learning model on dataset',
    'computer_science_ai', 'complex', mlComp.id
  );
  mlTrainingTask.requiredKnowledge = [mlKnowledge.id, deepLearning.id, linearAlg.id, probability.id];
  mlTrainingTask.requiredSkills = [pythonSkill.id, statsSkill.id, dataCleaning.id];
  mlTrainingTask.requiredTools = [pythonTool.id, jupyterTool.id];
  mlTrainingTask.inputs = [
    { id: uid(), name: 'Training Data', type: 'file', format: 'csv', description: 'Labeled training dataset', required: true },
    { id: uid(), name: 'Model Config', type: 'parameter', description: 'Hyperparameters', required: true },
  ];
  mlTrainingTask.outputs = [
    { id: uid(), name: 'Trained Model', type: 'file', format: 'pkl', description: 'Serialized model', required: true },
    { id: uid(), name: 'Metrics', type: 'data', format: 'json', description: 'Evaluation metrics', required: true },
    { id: uid(), name: 'Report', type: 'file', format: 'html', description: 'Training report', required: false },
  ];
  mlTrainingTask.workflow = [
    { id: uid(), order: 1, name: 'Load data', action: 'Load and inspect dataset', requiredKnowledge: [], requiredSkills: [pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Clean data', action: 'Handle missing values, outliers', requiredKnowledge: [], requiredSkills: [dataCleaning.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Feature engineering', action: 'Create and select features', requiredKnowledge: [mlKnowledge.id], requiredSkills: [pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Split data', action: 'Train/validation/test split', requiredKnowledge: [probability.id], requiredSkills: [], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Train model', action: 'Fit model on training data', requiredKnowledge: [mlKnowledge.id], requiredSkills: [pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 6, name: 'Evaluate', action: 'Evaluate on validation set', requiredKnowledge: [probability.id], requiredSkills: [statsSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 7, name: 'Tune hyperparameters', action: 'Optimize model parameters', requiredKnowledge: [mlKnowledge.id], requiredSkills: [pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
  ];
  mlTrainingTask.verification = [
    { id: uid(), name: 'Model Accuracy', method: 'testing', description: 'Check model performance', checkType: 'test', expectedResults: ['Accuracy > 85%'], onFail: 'retry' },
    { id: uid(), name: 'Overfitting Check', method: 'calculation', description: 'Compare train/val performance', checkType: 'calculation', expectedResults: ['Gap < 5%'], onFail: 'retry' },
  ];
  mlTrainingTask.failureModes = [
    { id: uid(), name: 'Overfitting', description: 'Model performs well on train but poorly on test', cause: 'Model too complex or insufficient data', symptom: 'High train accuracy, low test accuracy', severity: 'high', probability: 'likely', detectionMethod: 'Learning curves', prevention: ['Regularization', 'Cross-validation', 'More data'], mitigation: ['Simplify model', 'Add regularization', 'Get more data'], occurredBefore: true },
    { id: uid(), name: 'Data Leakage', description: 'Information from test set leaks into training', cause: 'Improper data splitting', symptom: 'Unusually high performance', severity: 'critical', probability: 'possible', detectionMethod: 'Careful validation', prevention: ['Proper train/test split', 'Time-based split'], mitigation: ['Fix data pipeline', 'Re-split data'], occurredBefore: false },
  ];

  // ═══════════════════════════════════════════
  // PROFESSION 4: ECONOMIST
  // ═══════════════════════════════════════════

  const ecoProf = pcm.createProfession(
    'Economist',
    'Analyze economic systems, forecast trends, inform policy',
    'economics',
    '📈', '#059669'
  );

  const ecoForecastSpec = pcm.createSpecialization(
    'Economic Forecasting',
    'Predict economic indicators and trends',
    ecoProf.id
  );

  const forecastComp = pcm.createCompetency(
    'Econometric Modeling',
    'Build and estimate econometric models',
    'economics',
    [ecoProf.id]
  );
  ecoForecastSpec.competencies.push(forecastComp.id);

  const forecastTask = pcm.createTask(
    'Economic Forecast',
    'Forecast economic indicator (GDP, inflation, etc.)',
    'economics', 'complex', forecastComp.id
  );
  forecastTask.requiredKnowledge = [econometrics.id, probability.id];
  forecastTask.requiredSkills = [statsSkill.id, pythonSkill.id, dataCleaning.id];
  forecastTask.requiredTools = [pythonTool.id, jupyterTool.id, excelTool.id];
  forecastTask.inputs = [
    { id: uid(), name: 'Historical Data', type: 'file', format: 'csv', description: 'Time series data', required: true },
    { id: uid(), name: 'Model Selection', type: 'parameter', description: 'Model type (ARIMA, VAR, etc.)', required: true },
  ];
  forecastTask.outputs = [
    { id: uid(), name: 'Forecast', type: 'data', format: 'csv', description: 'Forecasted values', required: true },
    { id: uid(), name: 'Confidence Intervals', type: 'data', format: 'csv', description: 'Uncertainty bounds', required: true },
    { id: uid(), name: 'Report', type: 'file', format: 'pdf', description: 'Forecast report', required: false },
  ];
  forecastTask.workflow = [
    { id: uid(), order: 1, name: 'Collect data', action: 'Gather historical economic data', requiredKnowledge: [], requiredSkills: [dataCleaning.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Clean data', action: 'Handle missing values, seasonality', requiredKnowledge: [], requiredSkills: [dataCleaning.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Explore data', action: 'Visualize and understand patterns', requiredKnowledge: [probability.id], requiredSkills: [statsSkill.id], requiredTools: [jupyterTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Select model', action: 'Choose appropriate econometric model', requiredKnowledge: [econometrics.id], requiredSkills: [statsSkill.id], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Estimate model', action: 'Fit model to data', requiredKnowledge: [econometrics.id], requiredSkills: [pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 6, name: 'Validate model', action: 'Check model assumptions', requiredKnowledge: [econometrics.id], requiredSkills: [statsSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 7, name: 'Generate forecast', action: 'Produce forecasts with confidence intervals', requiredKnowledge: [], requiredSkills: [pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 8, name: 'Scenario analysis', action: 'Run what-if scenarios', requiredKnowledge: [], requiredSkills: [statsSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
  ];
  forecastTask.verification = [
    { id: uid(), name: 'Residual Analysis', method: 'calculation', description: 'Check residuals are white noise', checkType: 'calculation', expectedResults: ['No autocorrelation'], onFail: 'retry' },
    { id: uid(), name: 'Out-of-sample Test', method: 'testing', description: 'Test on holdout data', checkType: 'test', expectedResults: ['RMSE within bounds'], onFail: 'retry' },
  ];
  forecastTask.failureModes = [
    { id: uid(), name: 'Structural Break', description: 'Underlying relationship changes', cause: 'Economic regime change', symptom: 'Sudden forecast error', severity: 'high', probability: 'possible', detectionMethod: 'Chow test', prevention: ['Monitor for breaks', 'Use rolling windows'], mitigation: ['Re-estimate model', 'Include break dummies'], occurredBefore: false },
  ];

  // ═══════════════════════════════════════════
  // PROFESSION 5: PROJECT MANAGER
  // ═══════════════════════════════════════════

  const pmProf = pcm.createProfession(
    'Project Manager',
    'Plan, execute, and deliver projects on time and budget',
    'project_management',
    '📋', '#ea580c'
  );

  const pmPlanningSpec = pcm.createSpecialization(
    'Project Planning',
    'Create project plans, WBS, schedules',
    pmProf.id
  );

  const pmPlanningComp = pcm.createCompetency(
    'Project Planning & Scheduling',
    'Create comprehensive project plans',
    'project_management',
    [pmProf.id]
  );
  pmPlanningSpec.competencies.push(pmPlanningComp.id);

  const wbsTask = pcm.createTask(
    'Create WBS',
    'Decompose project into work packages',
    'project_management', 'moderate', pmPlanningComp.id
  );
  wbsTask.requiredKnowledge = [projectManagement.id];
  wbsTask.requiredSkills = [projectPlanningSkill.id];
  wbsTask.requiredTools = [excelTool.id, wordTool.id];
  wbsTask.inputs = [
    { id: uid(), name: 'Project Scope', type: 'parameter', description: 'Project scope statement', required: true },
    { id: uid(), name: 'Requirements', type: 'data', description: 'Project requirements', required: true },
  ];
  wbsTask.outputs = [
    { id: uid(), name: 'WBS', type: 'file', format: 'xlsx', description: 'Work Breakdown Structure', required: true },
    { id: uid(), name: 'WBS Dictionary', type: 'file', format: 'docx', description: 'Detailed work package descriptions', required: false },
  ];
  wbsTask.workflow = [
    { id: uid(), order: 1, name: 'Identify deliverables', action: 'List all project deliverables', requiredKnowledge: [], requiredSkills: [projectPlanningSkill.id], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Decompose deliverables', action: 'Break down into work packages', requiredKnowledge: [], requiredSkills: [projectPlanningSkill.id], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Estimate effort', action: 'Estimate effort for each work package', requiredKnowledge: [], requiredSkills: [projectPlanningSkill.id], requiredTools: [excelTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Assign resources', action: 'Assign resources to work packages', requiredKnowledge: [], requiredSkills: [projectPlanningSkill.id], requiredTools: [excelTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Create schedule', action: 'Develop project schedule', requiredKnowledge: [], requiredSkills: [projectPlanningSkill.id], requiredTools: [excelTool.id], inputs: [], outputs: [], verification: [] },
  ];
  wbsTask.verification = [
    { id: uid(), name: 'Completeness Check', method: 'review', description: 'Verify all scope covered', checkType: 'review', expectedResults: ['100% scope covered'], onFail: 'retry' },
    { id: uid(), name: 'Estimation Review', method: 'review', description: 'Peer review of estimates', checkType: 'review', expectedResults: ['Realistic estimates'], onFail: 'retry' },
  ];

  // ═══════════════════════════════════════════
  // PROFESSION 6: AI ENGINEER
  // ═══════════════════════════════════════════

  const aiProf = pcm.createProfession(
    'AI Engineer',
    'Build AI/ML systems, deploy models, manage AI infrastructure',
    'computer_science_ai',
    '🤖', '#6366f1'
  );

  const aiMLOpsSpec = pcm.createSpecialization(
    'MLOps',
    'Machine learning operations and deployment',
    aiProf.id
  );

  const aiMLOpsComp = pcm.createCompetency(
    'Model Deployment & Monitoring',
    'Deploy ML models to production and monitor',
    'computer_science_ai',
    [aiProf.id, dsProf.id]
  );
  aiMLOpsSpec.competencies.push(aiMLOpsComp.id);

  const modelDeployTask = pcm.createTask(
    'Model Deployment',
    'Deploy trained model to production',
    'computer_science_ai', 'complex', aiMLOpsComp.id
  );
  modelDeployTask.requiredKnowledge = [mlKnowledge.id, softwareArch.id];
  modelDeployTask.requiredSkills = [pythonSkill.id, versionControl.id];
  modelDeployTask.requiredTools = [pythonTool.id, vscodeTool.id, gitTool.id];
  modelDeployTask.inputs = [
    { id: uid(), name: 'Trained Model', type: 'file', format: 'pkl', description: 'Serialized model', required: true },
    { id: uid(), name: 'API Spec', type: 'parameter', description: 'API requirements', required: true },
  ];
  modelDeployTask.outputs = [
    { id: uid(), name: 'API Service', type: 'file', format: 'python', description: 'Model serving API', required: true },
    { id: uid(), name: 'Docker Image', type: 'file', format: 'docker', description: 'Containerized service', required: true },
    { id: uid(), name: 'Monitoring Dashboard', type: 'file', format: 'html', description: 'Model monitoring', required: false },
  ];
  modelDeployTask.workflow = [
    { id: uid(), order: 1, name: 'Create serving API', action: 'Build REST API for model', requiredKnowledge: [softwareArch.id], requiredSkills: [pythonSkill.id], requiredTools: [vscodeTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Containerize', action: 'Create Docker container', requiredKnowledge: [], requiredSkills: [versionControl.id], requiredTools: [gitTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Write tests', action: 'Create integration tests', requiredKnowledge: [], requiredSkills: [testingSkill.id], requiredTools: [vscodeTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Deploy', action: 'Deploy to cloud/edge', requiredKnowledge: [], requiredSkills: [versionControl.id], requiredTools: [gitTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Set up monitoring', action: 'Configure model monitoring', requiredKnowledge: [], requiredSkills: [], requiredTools: [], inputs: [], outputs: [], verification: [] },
  ];
  modelDeployTask.verification = [
    { id: uid(), name: 'API Test', method: 'testing', description: 'Test API endpoints', checkType: 'test', expectedResults: ['All endpoints respond correctly'], onFail: 'retry' },
    { id: uid(), name: 'Load Test', method: 'testing', description: 'Test under load', checkType: 'test', expectedResults: ['Handles expected traffic'], onFail: 'retry' },
  ];

  // ═══════════════════════════════════════════
  // PROFESSION 7: CREATIVE DESIGNER
  // ═══════════════════════════════════════════

  const crProf = pcm.createProfession(
    'Creative Designer',
    'Create visual content, UI/UX designs, and multimedia',
    'creative',
    '🎨', '#ec4899'
  );

  const uiuxSpec = pcm.createSpecialization(
    'UI/UX Design',
    'Design user interfaces and experiences',
    crProf.id
  );

  const uiuxComp = pcm.createCompetency(
    'Interface Design',
    'Design intuitive and beautiful interfaces',
    'creative',
    [crProf.id]
  );
  uiuxSpec.competencies.push(uiuxComp.id);

  // ═══════════════════════════════════════════
  // PROFESSION 8: ACADEMIC RESEARCHER
  // ═══════════════════════════════════════════

  const arProf = pcm.createProfession(
    'Academic Researcher',
    'Conduct research, publish papers, advance knowledge',
    'academic_research',
    '📚', '#8b5cf6'
  );

  const paperSpec = pcm.createSpecialization(
    'Research Paper Writing',
    'Write and publish academic papers',
    arProf.id
  );

  const paperComp = pcm.createCompetency(
    'Scientific Writing',
    'Write clear, rigorous scientific papers',
    'academic_research',
    [arProf.id]
  );
  paperSpec.competencies.push(paperComp.id);

  const paperTask = pcm.createTask(
    'Write Research Paper',
    'Write academic paper for publication',
    'academic_research', 'expert', paperComp.id
  );
  paperTask.requiredKnowledge = [probability.id];
  paperTask.requiredSkills = [researchSkill.id, writingSkill.id];
  paperTask.requiredTools = [wordTool.id, pythonTool.id];
  paperTask.inputs = [
    { id: uid(), name: 'Research Data', type: 'file', format: 'csv', description: 'Experimental data', required: true },
    { id: uid(), name: 'Hypothesis', type: 'parameter', description: 'Research hypothesis', required: true },
  ];
  paperTask.outputs = [
    { id: uid(), name: 'Paper Draft', type: 'file', format: 'docx', description: 'Research paper', required: true },
    { id: uid(), name: 'Figures', type: 'file', format: 'pdf', description: 'Publication figures', required: true },
    { id: uid(), name: 'Supplementary', type: 'file', format: 'zip', description: 'Supplementary materials', required: false },
  ];
  paperTask.workflow = [
    { id: uid(), order: 1, name: 'Literature review', action: 'Review relevant literature', requiredKnowledge: [], requiredSkills: [researchSkill.id], requiredTools: [], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 2, name: 'Analyze data', action: 'Perform statistical analysis', requiredKnowledge: [probability.id], requiredSkills: [statsSkill.id, pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 3, name: 'Create figures', action: 'Generate publication figures', requiredKnowledge: [], requiredSkills: [pythonSkill.id], requiredTools: [pythonTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 4, name: 'Write introduction', action: 'Write introduction and motivation', requiredKnowledge: [], requiredSkills: [writingSkill.id], requiredTools: [wordTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 5, name: 'Write methods', action: 'Describe methodology', requiredKnowledge: [], requiredSkills: [writingSkill.id], requiredTools: [wordTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 6, name: 'Write results', action: 'Present findings', requiredKnowledge: [], requiredSkills: [writingSkill.id], requiredTools: [wordTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 7, name: 'Write discussion', action: 'Interpret and discuss results', requiredKnowledge: [], requiredSkills: [writingSkill.id], requiredTools: [wordTool.id], inputs: [], outputs: [], verification: [] },
    { id: uid(), order: 8, name: 'Peer review', action: 'Internal review before submission', requiredKnowledge: [], requiredSkills: [], requiredTools: [], inputs: [], outputs: [], verification: [] },
  ];
  paperTask.verification = [
    { id: uid(), name: 'Citation Check', method: 'inspection', description: 'Verify all citations', checkType: 'inspection', expectedResults: ['All claims cited'], onFail: 'retry' },
    { id: uid(), name: 'Statistical Review', method: 'review', description: 'Review statistical methods', checkType: 'review', expectedResults: ['Methods appropriate'], onFail: 'retry' },
  ];

  // Add experiences
  pcm.recordExperience(
    schematicTask.id,
    'Designed LED driver circuit',
    'Circuit worked first time, met all specs',
    'success',
    'Simple buck converter topology was sufficient for this application',
    [kicadTool.id],
    120
  );

  pcm.recordExperience(
    pcbLayoutTask.id,
    'Routed 4-layer PCB for sensor board',
    'First attempt had impedance mismatch',
    'partial',
    'Need to calculate trace impedance before routing, not after',
    [kicadTool.id],
    480
  );

  pcm.recordExperience(
    mlTrainingTask.id,
    'Trained image classifier',
    'Overfitting on small dataset',
    'failure',
    'Data augmentation and regularization critical for small datasets',
    [pythonTool.id, jupyterTool.id],
    360
  );

  pcm.recordExperience(
    forecastTask.id,
    'Forecasted GDP growth',
    'Model performed well in-sample but poorly out-of-sample',
    'partial',
    'Structural break in 2020 broke historical relationships. Need regime-switching model.',
    [pythonTool.id, jupyterTool.id],
    240
  );
}

// ═══════════════════════════════════════════════
// HELPER
// ═══════════════════════════════════════════════

let _uidCounter = 0;
function uid(): string {
  _uidCounter++;
  return `pcmio_${Date.now().toString(36)}_${_uidCounter}`;
}

export function getPCMStats() {
  return pcm.getStats();
}
