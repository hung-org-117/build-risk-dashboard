Date of publication xxxx 00, 0000, date of current version xxxx 00, 0000.
Digital Object Identifier 10.1109/ACCESS.2017.DOI

# Uncertainty-Aware Prediction of

# Software Defect Risks from Code

# Changes in CI/CD Pipelines

**THI-HUONG-GIANG VU** 1^1 **(Member, IEEE), MANH-TUAN NGUYEN**^1 **, AND VAN-DUY PHAN**^1**.**
Hanoi University of Science and Technology, 11615 Hanoi, Vietnam
Corresponding author: Thi-Huong-Giang Vu (e-mail: giangvth@soict.hust.edu.vn).

The project is funded by the Hanoi University of Science and Technology, under Grant No. T2022-PC-045.

```
ABSTRACT This paper address a method for uncertainty-aware defect risk prediction directly from code
changes in DevOps CI/CD pipelines. The method takes four streams of DevOps artifacts as input of a dual-
branch deep learning architecture designed to predict defect-prone changes with calibrated risk scores and
quantified uncertainty. The first branch is a two-layer Long Short-Term Memory that learns the evolution
of artifact-level features across successive commits and deployments. The second is a Bayesian Tabular
Multi-Layer Perceptron that captures the synergy among features within each development snapshot. The
probabilistic outputs of both branches are incorporated into a shared Bayesian calibration layer to generate
final defect risk predictions. Experiments on a large-scale set of 892,193 CircleCI builds show that our
approach outperforms standalone LSTM and MLP baselines. Using metrics for predictive quality, reliability,
and low-false-positive practicality, the proposed method consistently demonstrates superior calibration and
robustness across all experimental scenarios, enhancing trustworthy defect risk assessment in DevOps
pipelines.
```
```
INDEX TERMS DevOps, risk analysis, forecast uncertainty
```
```
I. INTRODUCTION
```
Modern software engineering increasingly adopts DevOps, a
methodology that emphasizes automation, collaboration, and
continuous feedback between development and operations
teams. DevOps is realized through continuous integration and
continuous deployment (CI/CD) pipelines. Each execution of
a CI/CD pipeline constitutes a complete iteration from code
change to production deployment, called a deployment cycle.
The high frequency and partial automation of these cycles en-
able rapid, iterative releases, often occurring multiple times
per day. However, this velocity also amplifies software defect
risks, i.e., the combined effect of the probability of deviations
from expected requirements arising and the severity of their
impacts on deployed systems. These risks stem from code
changes, configuration gaps, or insufficient testing, and can
accumulate across successive deployments as development
trends and operational practices evolve. They also emerge
through complex cross-dependencies among code, build and
test outcomes, deployment frequency, and human factors.
Left unchecked, these defects degrade software quality and
lead to costly rollbacks, delayed releases, and reduced devel-

```
oper productivity.
In CI/CD pipelines, the temporal gap between defect in-
troduction and defect detection is compressed. Build failures
serve as the primary mechanism through which defects are
surfaced and prevented from reaching production. A failed
build indicates that the changes violated one or more quality
gates such as compilation errors, test failures, or security
vulnerabilities. Software defect risk in CI/CD context can
be conceptualized as the probability of a build failure. A
failed build thus represents an observable manifestation of
underlying defect introduction. However, a successful build
does not guarantee defect absence. It only indicates that no
defects were detected by the specific verification processes
in the pipeline. Build-based defect risk prediction focuses on
defects that are detectable within the CI/CD process rather
than all potential defects, and the extent of defect detection
coverage depends on the comprehensiveness of the pipeline.
Accurately predicting such risks requires using the full
spectrum of DevOps artifacts, i.e., semantically rich data
entities generated and circulated throughout the deployment
cycle across four main streams: code, test, team activity, and
```

monitoring. Since each artifact reflects a distinct dimension
of risk, they serve as a valuable basis for monitoring and man-
aging software defect risks. Traditional approaches, however,
rely on only a narrow subset, such as static code metrics,
testing outcomes, or historical bug reports. Although useful,
these artifacts pertain to isolated pipeline stages and thus
offer only a partial perspective on defect risks. Consequently,
existing predictions remain misaligned with the continuous
and interdependent nature of modern DevOps environments,
leaving critical research gaps.
First, existing approaches rarely model the temporal evolu-
tion of artifacts across deployments, overlooking how defect
risks accumulate and shift over successive cycles. Second,
they often overlook cross-artifact synergy in risk formation
within a deployment, making it easy to miss defects arising
from multiple artifacts. Third, they generally disregard the
estimation and calibration of predictive uncertainty, render-
ing predictions overconfident and unreliable when artifacts
deviate or drift in fast-paced CI/CD pipelines.
To address these gaps, we propose a novel method for
timely and continuous defect risk prediction in CI/CD
pipelines. Our approach directly learns uncertainty-aware
defect risk predictions from DevOps artifacts spanning the
entire deployment cycle.
Concretely, we aggregate four artifact streams, including
source code changes, test and coverage results, team ac-
tivity, and DevOps monitoring, into development snapshots
aligned to each build. On top of these snapshots, we model
two complementary views of risk: (i) a temporal view that
captures how artifact-level features evolve across recent de-
ployments, and (ii) a synergy view that captures cross-artifact
interactions within the current deployment. The two views
are instantiated via a two-layer LSTM with attention and a
Bayesian tabular multi-layer perceptron, respectively. They
are then fused through an uncertainty-weighted calibration
layer that yields calibrated probabilities with reliable confi-
dence estimates.
This study makes the following key contributions:

- We identify four major artifact streams and define
    risk-related features that reflect temporal evolution and
    cross-artifact dependencies in CI/CD pipelines.
- We propose a dual-branch deep learning architecture to
    model distinct risk dependencies in DevOps artifacts.
    One branch uses an LSTM to capture temporal dynam-
    ics, while the other employs a Bayesian tabular MLP
    to model multi-artifact interactions. These branches are
    integrated through a Bayesian calibration layer that
    yields well-calibrated risk predictions with quantified
    uncertainty.
- We demonstrate that our approach improves low–false-
    positive recall and probability calibration over strong
    baselines on two datasets, including a curated collection
    of open-source repositories (2021–2025) and a large-
    scale public CI dataset of 892,193 CircleCI builds.
The remainder of this paper is organized as follows.
Section II reviews related work. Section III introduces the

```
artifact streams and feature construction. Section IV presents
our architecture, focusing on the dual-branch design and
uncertainty-weighted fusion. Section V details the training
procedures, calibration methods, and experimental results,
including ablation studies. Finally, Section VI concludes the
paper and outlines directions for future research.
```
```
II. RELATED WORK
A. DEFECT PREDICTION FROM CODE CHANGES
Traditional approaches to defect prediction primarily relied
on static code metrics including lines of code, cyclomatic
complexity, coupling measures, and cohesion indicators that
computed at the file or class level to characterize code quality
and predict defect likelihood. The works such as [1], [2]
and [3], focused on code-level metrics derived from version
control systems. While these metrics capture key aspects of
technical change characteristics, code-only approaches are
insufficient in DevOps contexts. They capture only snapshot
characteristics of code at a single point in time, ignoring
the dynamic nature of software evolution. They should be
complemented by additional factors, such as distinguishing
configuration changes from application code changes.
Just-in-time (JIT) defect prediction, introduced by [4] and
extended by [5], [6] incorporates process metrics alongside
code metrics. JIT approaches add features such as fix status
(whether a change is a bug fix), change purpose (extracted
from commit messages), and temporal information. JIT pro-
cess metrics are typically limited to commit-level metadata
rather than comprehensive DevOps pipeline artifacts.
```
```
B. CODE CHANGE ANALYSIS
In [7], the approach focused on the use of commit message
textual analysis for predicting build outcomes in CI/CD en-
vironments. The results demonstrates that natural language
processing techniques applied to commit messages can cap-
ture developer intent and change rationale that complement
quantitative code metrics.
[8] extended CI/CD defect prediction by investigating
the impact of code ownership patterns on build outcomes,
specifically examining how ownership of DevOps artifacts
(CI/CD configuration files, deployment scripts) influences
build success rates. These findings implied that team com-
position and ownership patterns are critical risk factors in
CI/CD environments.
Recent research has increasingly recognized that defects
are not inherent properties of code structure alone but rather
emerge through the change process. Recent work on DevOps-
aware defect prediction, such as [9], [10] and [11] have begun
integrating build logs and CI/CD pipeline data. These ap-
proaches acknowledge that defects in DevOps environments
cannot be predicted solely from code but must account for
the broader pipeline context.
```

**C. MACHINE LEARNING APPROCHES FOR DEVOPS
RISK PREDICTION**
The application of machine learning to defect prediction has
evolved from simple statistical models [12] to sophisticated
deep learning architectures, with recent work exploring en-
semble methods [13] [14], neural networks [15] [16], and hy-
brid approaches that combine multiple modeling paradigms.
Deep learning approaches to defect prediction, such as
DeepJIT [15] and CC2Vec [16] represent another approach
that learns representations directly from code changes us-
ing neural networks. DeepJIT processes code changes and
commit messages through convolutional and recurrent neural
networks, while CC2Vec learns distributed representations
of code changes. These approaches achieve impressive per-
formance by automatically learning relevant features from
raw data rather than relying on hand-crafted metrics. They
remain limited to code-centric information, processing only
source code diffs and commit messages. [17] provided a
comprehensive survey of deep learning approaches for defect
prediction, noting that models incorporating temporal change
patterns through recurrent neural networks outperform static
feature-based models. These findings underscore that defect
prediction must model not only what the code is but also how
it evolved to its current state.
A limitation of existing deep learning approaches for de-
fect prediction is their treatment as black-box models that
provide point predictions without uncertainty quantification.
Recent works, [18] [19] [20] have begun addressing this
limitation by incorporating uncertainty quantification into
neural network predictions. [19] demonstrated that Monte
Carlo dropout provides a practical approximation to Bayesian
inference, enabling estimation of model uncertainty through
multiple stochastic forward passes. [21] applied Bayesian
uncertainty quantification methods for predicting safety mis-
behaviors.

**III. DEVOPS ARTIFACT MODEL**
To enable reliable defect risk prediction in DevOps pipelines,
we construct a DevOps Artifact Model that systematically
organizes the heterogeneous artifacts generated during con-
tinuous integration and deployment. This model serves as a
conceptual and data foundation for our learning architecture,
linking the operational evidence of software evolution to risk-
oriented representations. It encapsulates the DevOps process
through two complementary components: (i) defect-risk-
oriented artifact streams, which define the major data sources
and their temporal organization across code, test, team,
and monitoring dimensions, and (ii) artifact features, which
transform raw artifacts into quantitative descriptors suitable
for learning risk dependencies. Together, these components
bridge the gap between diverse DevOps evidence and model-
ready input for uncertainty-aware defect-risk prediction.

**A. DEFECT RISK-ORIENTED DATA SOURCES**
Software defect risks originating from code change cannot be
adequately characterized through isolated metrics or single-

```
FIGURE 1. Factors related to defect risk manifestation.
```
```
dimensional analysis. Our approach formalizes defect risk as
the confluence of technical, human and contextual factors.
This decomposition is not arbitrary but rather reflects the
causal pathways through which code changes introduce de-
fects. A change may contain latent defects due to its inherent
complexity, which may escape detection of testing (technical
factor), particularly when made by inexperienced developers
(human factor), in a project with immature quality processes
(contextual factor). Each dimension provides essential in-
formation that enhances the understanding of how defects
emerge, evolve, and manifest throughout the entire deploy-
ment lifecycle. This comprehensive understanding serves as
the foundation for defining our four-stream data sources.
In DevOps, an artifact refers to any intermediate prod-
uct, data, or output that is generated, collected, managed,
analyzed, or used throughout the DevOps lifecycle (CI/CD
pipeline and system operations). DevOps artifacts ensure that
integration, testing, deployment, and operation of software
are smooth, controlled, and reproducible. They are produced
and propagated through the main data flows of the software
development and operations lifecycle, referred to as DevOps
artifact streams. Each stream originates from a system or tool
at a particular stage in the pipeline and carries artifacts along
with metadata to support subsequent steps.
In the scope of this paper, we focus on artifact streams
generated from specific DevOps stages: the Plan/Code phase
produces the Team activity stream; the Code/Release/Deploy
phase produces the Source code stream; the Build/Test phase
produces the Test and coverage stream; the Operate/Monitor
phase produces the DevOps monitoring stream.
```

1) Source code stream (Xcode)

The source-code stream models the technical change signal
captured by the Version Control System (VCS). It measures
what code changed and how those changes are organized
across files and commits. This stream comprises three arti-
facts: commit, source code change, and DevOps configura-
tion change.

```
a: Commit (A 1 )
```
A commit represents an atomic code change recorded in the
version control system, including metadata such as author
and timestamp. This artifact captures the evolution of the
delivery process and the frequency of code integrations over
time.

- Commit volume measures the number of commits asso-
    ciated with a build or over a given time period, indicat-
    ing the intensity of code integration.
- DevOps configuration commits capture commits that
    modify CI/CD or configuration files, reflecting changes
    to the delivery pipeline or operational setup.

b: Source code change (A 2 )
A source code change represents modifications to program
logic between revisions, emphasizing the magnitude and
scope of edits across source code files.

- Code churn sums the lines of code added and deleted
    across revisions in a build. It serves as a standard indi-
    cator of change magnitude.
- Change scope captures the number of source files af-
    fected within a build to represent the breadth of a change
    set.

c: DevOps file change (A 3 )
This artifact focuses on edits to configuration or pipeline files
that influence build, test, or deployment behavior.

- DevOps churn measures the size of edits applied to
    CI/CD or configuration per build. It quantifies the in-
    tensity of configuration updates and indicates the extent
    of process-level change.
- DevOps configuration file change counts the number of
    CI/CD or configuration files edited in a build or over
    the project history. This represents the evolution of the
    delivery pipeline and automation assets.

2) Test and coverage stream (Xtest)
The test and coverage stream addresses the adequacy of ver-
ification for technical factor by capturing how code changes
are validated before deployment. This stream examines arti-
facts generated during automated build and testing processes.
There are three main artifacts in this stream.

```
a: Build outcome (A 4 )
```
This artifact records the immediate result and short-term
reliability of build executions.

- Build result is the binary outcome of the current build,
    indicating success or failure as reported by the CI
    pipeline.
- Previous build result is the outcome of the most recent
    preceding build, providing short-term contextual infor-
    mation about pipeline stability.
- Recent failure rate is the proportion of failed builds over
    a sliding window of recent executions, reflecting short-
    term instability in the build process.

```
b: Test expectation (A 5 )
This artifact defines the expected performance threshold of
the build process.
```
- Expected build success rate is the target success rate
    established by the development team, serving as a ref-
    erence benchmark for test coverage and build quality.

```
c: Failure log (A 6 )
This artifact captures historical failure patterns associated
with individual developers or DevOps activities.
```
- Committer failure history is the cumulative number or
    rate of failed builds associated with a specific committer,
    reflecting personal reliability.
- Committer recent failure history is the count or rate of
    failed builds within a sliding time window for a given
    committer, capturing short-term delivery risk.
- DevOps build failure rate is the aggregate failure rate of
    DevOps-related builds at the project level, representing
    long-term trends in pipeline reliability.

```
3) Team activity stream (Xteam)
The team activity stream captures the human factor by
modeling who makes changes and how team composition
and coordination patterns influence defect risks. This stream
extracts metadata and documentation related to team plan-
ning and development activities such as staffing composition,
contributor experience, and distribution of ownership across
the repository.
```
```
a: Staffing plan (A 7 )
This artifact characterizes the contributor base and the diver-
sity of participation within and across builds.
```
- Contributor count captures the number of distinct devel-
    opers participating in a build or over the project period,
    reflecting the level of team involvement.
- DevOps participation measures the extent of contributor
    involvement in CI/CD, or configuration changes, indi-
    cating DevOps engagement within the team.
- Contribution concentration quantifies how contribu-
    tions are distributed among developers, highlighting
    whether work is dominated by a few core contributors
    or shared more evenly.

```
b: Responsibility assignment matrix (A 8 )
This artifact maps roles and responsibilities to team members
in the delivery process.
```

- Committer experience measures the accumulated contri-
    bution history of committers to indicate their familiarity
    with the codebase and processes.
- Role continuity identifies recurring ownership across
    builds, capturing short-term stability in assignment of
    integration or delivery responsibilities.

c: Contribution log (A 9 )
This artifact captures how work is distributed and shared
across developers.

- Ownership distribution measures the balance of contri-
    butions across developers, including concentration pat-
    terns following the Pareto principle.
- Author overlap assesses how frequently the same de-
    velopers appear across different components or time
    periods, indicating cross-area collaboration.
- DevOps focus identifies whether a build is primar-
    ily driven by contributors focused on DevOps-related
    changes.
- Contribution skewness quantifies inequality in contri-
    bution volume, both overall and within DevOps-related
    activities.

4) Monitoring stream (Xmonitoring)

The monitoring stream addresses the contextual factor by
capturing when and where code changes occur within the
project lifecycle and operational environment. This stream
recognizes that defect risks are inherently context-dependent:
identical code changes carry different risk profiles depending
on project maturity, technology stack, and integration pro-
cesses. It contains four artifacts.

a: Maturity model (A 10 )
This artifact reflects project visibility and lifecycle maturity.

- Community engagement measures external interest and
    adoption through repository popularity and reuse sig-
    nals.
- Project maturity summarizes the overall development
    stage or stability of the project based on a defined
    maturity model.

```
b: Technology (A 11 )
```
This artifact describes the technological foundation of the
project.

- Primary technology identifies the main programming
    language or platform defining the project’s implemen-
    tation base.

c: Build history (A 12 )
This artifact characterizes the temporal context and historical
behavior of builds.

- Historical build activity measures cumulative and prior
    build counts to represent the project’s integration vol-
    ume over time.
       - Temporal pattern encodes build occurrence across
          weekly and daily cycles to capture recurring activity
          trends.
       - Build type frequency tracks the share of builds associ-
          ated with DevOps or automation-related processes.

```
d: Change request (A 13 )
This artifact describes the integration of external code
changes.
```
- Pull request integration identifies builds triggered by
    pull requests and measures their proportion relative to
    direct commits, indicating reliance on peer review or
    external contributions.

```
B. DEVOPS ARTIFACTS’ CHARACTERISTICS
The effectiveness of defect risk prediction in CI/CD pipelines
fundamentally depends on how we represent and model the
relationships among DevOps artifacts. DevOps environments
exhibit two distinct complementary patterns of artifact be-
havior that must be explicitly modeled.
```
```
1) Temporal evolution
The emporal evolution characterizes how certain artifacts
change and accumulate information across successive de-
ployment cycles, creating historical trajectories that reveal
trends, degradation patterns, and momentum in software
quality. The second pattern, cross-artifact synergy, describes
how artifacts from different streams interact and combine to
jointly determine defect risks through complex interdepen-
dencies that cannot be understood by examining artifacts in
isolation.
The distinction between temporal evolution and cross-
artifact synergy is not merely a technical convenience but
reflects fundamental differences in how defect risks emerge
in DevOps environments. Temporal evolution captures the
dynamic nature of software development, where current risks
are influenced by historical patterns and recent trends. For
instance, a project experiencing increasing test failure rates
over the past ten builds faces higher defect risks than one with
stable test outcomes, even if the current build’s code metrics
are identical. This temporal dependency arises because dete-
riorating quality trends often signal underlying problems that
manifest gradually across multiple deployment cycles.
```
```
2) Cross-artifact synergy
Conversely, cross-artifact synergy captures the combinatorial
nature of defect causation. A complex code change (high
churn, many files modified) made by an inexperienced devel-
oper in an immature project represents substantially higher
risk than the sum of individual risk factors would suggest,
because these factors interact multiplicatively rather than ad-
ditively. The inexperienced developer may not recognize the
need for comprehensive testing given the change complexity,
while the immature project may lack automated safeguards
that would catch resulting defects.
```

Our approach explicitly distinguishes these two patterns
and constructs features tailored to capture each, enabling our
dual-branch architecture to model them through appropriate
neural network structures.
The design of temporal evolution and cross-artifact syn-
ergy features involves fundamental trade-offs between ex-
pressiveness (the ability to capture complex patterns) and
generalization (the ability to perform well on unseen data).
Overly specific features may overfit the training data, while
overly generic features may lack the discriminative power
needed for accurate risk prediction. Our feature engineering
addresses these trade-offs that guide feature construction and
selection. The artifacts in the Source code stream and the
Test and coverage stream exhibit characteristics of evolution
over time, while the artifacts in the remaining streams exhibit
characteristics of synergy.

**IV. DUAL-BRANCH PREDICTION ARCHITECTURE**
We propose an uncertainty-aware defect risk prediction ap-
proach for CI/CD pipelines that integrates both snapshot-
level and temporal perspectives. As illustrated in Fig. IV, the
overall architecture consists of four major blocks.
The preprocessing block extracts features from four De-
vOps artifact streams, aggregates and normalizes them per
commit/build into a collection of development snapshots.
Each snapshot represents the complete system state at a
given build, enriched with temporal indicators from the code
and test streams and contextual descriptors from the team
and monitoring streams. These development snapshots are
organized through two complementary schemes: (i) per-build
sequencing, which orders the development snapshots along
the commit/deploy timeline and augments them with tempo-
ral evolution features from the code and test streams; and (ii)
channel-wise separation, which partitions features by the four
artifact streams to form a multi-channel representation.
The output of the first scheme serves as input of the tem-
poral risk evolution learning block, which models sequential
risk dynamics across successive builds using recurrent and
attention layers. The output of the second scheme feeds the
cross-artifact risk synergy learning block, which captures
intra-build dependencies among heterogeneous DevOps arti-
facts through a Bayesian tabular network. These two learning
blocks together constitute a dual-branch prediction model:
one learns temporal risk evolution, and the other learns cross-
artifact risk interaction. The software defect risk inference
block consists of two layers. The uncertainty-weighted fusion
layer merges the probabilistic outputs from the two learning
blocks and adaptively calibrates their contributions based
on predictive confidence to produce a risk probability. This
probability is then passed to the final prediction layer, which
produces the binary defect risk classification output.

**A. PREPROCESSING BLOCK**
1) Aggregation
In this step, the discrete artifacts from the four streams are
unified and aligned to a common reference index (e.g., build,

```
commit, or branch identifiers with corresponding times-
tamps), so that each record consistently reflects the system
state at a given build time. This process not only consoli-
dates data but also extracts raw, build-level characteristics,
ensuring that each snapshot accurately represents the system
condition at a single point in time. Specifically, from the
source code stream, we obtain the number of commits, in-
tegration frequency, size and scope of code changes, and the
degree of impact on DevOps-related files; from the test and
coverage stream, we derive build success or failure outcomes,
recent failure ratios, stability expectations, and per-committer
failure histories; from the team activity stream, we compute
team size, DevOps contributor expertise, average experience,
contribution distribution, and ownership concentration; and
from the monitoring stream, we aggregate project popularity,
maturity indicators, dominant programming language, the
number and temporal distribution of builds, and the pro-
portion of builds triggered by pull requests. The output of
the aggregation step is a tabular dataset in which each row
corresponds to a build snapshot, and each column represents
an aggregated feature derived from the artifacts of the four
streams.
```
```
2) Normalization
After aggregation and feature extraction at the build level,
a normalization step is applied to ensure data consistency
and stability before feeding the model. Features are unified
in schema and data type (e.g., unit normalization, numeric
casting, and categorical encoding). For continuous or count-
based attributes such as code change size or recent fail-
ure ratios, values are normalized to a common scale using
methods such as min–max scaling or z–score standardiza-
tion. For proportion- or probability-based features such as
build success frequency, normalization mitigates differences
in scale across projects. Categorical attributes, such as the
dominant programming language or build state, are converted
into binary (one-hot) or dense embedding representations. In
addition, missing or outlier values are handled by replace-
ment with default, mean, or median values, by adding an
is_missing flag when necessary, or by applying statistical
imputation techniques.
The result of the normalization step is the development
snapshot (st), a normalized feature vector representing the
system state at build t:
st= Nrm(Aggr({Xtcode, Xtestt , Xteamt , Xmonitort })
```
## 

## (1)

```
The development snapshots stare stored sequentially over
time, forming a time-ordered dataset for the evolutionary
branch and static feature slices for the multi-channel branch.
Given an observation window of length k, the dataset is
defined as:
D ={st−k+1,...,st} (2)
Each st∈Rdis a normalized feature vector at build t,
where d is the feature dimensionality aggregated from the
four streams. The datasetD serves as the common input for
```

**FIGURE 2.** Dual-branch prediction architecture.

the two branches: the evolutionary branch consumes the full
sequence (st−k+1,...,st), while the multi-channel branch
takes the current snapshot st, partitioned into four input
channels.

3) Splitting
From the collected development snapshots, the input data for
the two branches are organized as follows.

a: Input of cross-feature synergy branch
The cross-feature synergy branch focuses on intra-build re-
lationships among all DevOps artifacts. It captures the struc-
tural synergy among heterogeneous features extracted from 4
streamsXtest,Xcode,Xteam,Xmonitoringat a specific build.
Therefore, the unified feature representation of the snap-
shot of build t is the input of this branch Isng= st
When training with a batch size of B, the input data for
cross-artifact synergy branch form a tensor of shapeRB×Ftot,
where Ftot denotes the total number of features extracted
from all 13 artifacts.

b: Input of temporal evolution branch
Let AT= {A 1 ,...,A 6 } denote the set of temporally evolv-
ing artifacts that reflect the dynamic behavior of the software
development process, primarily derived from the streams
Xcodeand Xtest(c.f. Section III). Each artifact Ai∈ AT
forms a time series, where Fiis the number of features
extracted from Ai:

```
sAi= (x^1 Ai,x^2 Ai,...,xkAi), xtAi∈RFi (3)
```
```
At time t, the aggregated feature vector stis constructed
by concatenating the artifact features along the feature di-
mension:
```
```
st= [xtA 1 ∥xtA 2 ∥···∥xtA 6 ], FtotT=
```
## X^6

```
i=
```
```
Fi (4)
```
```
where FtotT is the total number of concatenated features of
all artifacts in AT.
Thus, the input for temporal evolution branch is a time se-
ries of length k: Itmp= (st−k+1,st−k+2,...,st)∈Rk×Ftot,
where each stintegrates all information from the artifacts of
the two streams at time t. When training with a batch size of
B, the data are represented as a tensorRB×k×Ftot.
The preprocessing block therefore produces two groups of
model inputs: the sequence of snapshots (st−k+1,...,st) for
the evolutionary branch, and the unified feature vector Isngt
for the cross-artifact branch.
```
```
B. TEMPORAL RISK EVOLUTION LEARNING BLOCK
The temporal evolution branch, receives two streams—code
and test—that exhibit time-evolving characteristics. The ob-
jective of this branch is to preserve the temporal dynamics of
artifacts, enabling the model to observe the process of change
rather than a single static slice.
```
```
1) Feature extraction
The input sequence passes through stacked LSTM and at-
tention layers to learn temporal dependencies, followed by a
1D global average pooling (GAP1D) layer that aggregates
```

representations along the time axis to form the temporal
embedding:

```
Ztmp= GAP
```
## 

```
Attn(Nrm
```
## 

```
LSTM 64 (LSTM 128 (Itmp)))
```
## 

## (5)

Here, the first LSTM layer (128 units) performs coarse
filtering and retains major temporal variations within each
individual artifact, while the second LSTM layer (64 units)
refines these representations, learning cross-artifact interac-
tions and forming higher-level contextual embeddings.

2) Non-linear transformation
Next, the temporal representation is passed through a dense
layer with ReLU activation and a dropout mechanism. This
stage aims to abstract generalized patterns from the entire
artifact sequence, reducing local noise while preserving more
stable evolutionary trends relevant to defect risk prediction.

```
Htmp= Dropout
```
## 

## RELU

## 

```
Dense 64 (Ztmp)
```
## 

## (6)

3) Prediction
Finally, Htmppasses through two Bayesian dense layers to
produce predictive distributions, yielding both class proba-
bilities and associated uncertainty levels:

```
ˆtmpp = Softmax
```
## 

```
Flip 32
```
## 

```
Flip 64 (Htmp)
```
## 

## (7)

The Bayesian dense (DenseFlipout) layers learn a dis-
tribution over weights rather than single point estimates.
Consequently, each inference can yield slightly different
samples from this distribution. When the goal is only to
predict labels, a single inference is sufficient. However, to
exploit the Bayesian property for uncertainty quantification,
Monte Carlo sampling can be applied by performing multi-
ple stochastic forward passes and aggregating the resulting
output distributions. Specifically, by repeating T inference
samples through the Flipout layers, we obtain { ˆ(tmppi) }Ti=1,

from which the predictive mean ̄tmpp =T^1

## PT

```
i=1ˆp
```
(i)
tmpand
uncertainty (e.g., variance across probability dimensions) can
be estimated for subsequent fusion with the synergy branch.

**C. CROSS-FEATURE RISK SYNERGY LEARNING
BLOCK**
The cross-feature synergy branch receives four input streams
Xcode, Xtest, Xteam, and Xmonitoring. It focuses on cap-
turing the static risk characteristics at each build by learning
synergistic interactions among heterogeneous artifacts origi-
nating from all four streams. This branch complements the
temporal evolution branch by modeling intra-build depen-
dencies—such as team activity, project maturity, and tempo-
ral build history at the unified feature level. By integrating
contextual information from team and monitoring artifacts
with time-evolving features from code and test streams, it
provides a comprehensive representation of the overall defect
risk context. Initially, the artifact vectors are concatenated

```
to form a unified feature representation before being passed
through the subsequent learning layers.
```
```
1) Feature extraction
The four artifact vectors are sequentially passed through three
DenseFlipout layers with GELU activation, containing 128,
64, and 32 units, respectively. The first layer serves to enrich
the representation and extract synergistic correlations among
heterogeneous artifacts. The subsequent layers progressively
reduce dimensionality using a progressive reduction strat-
egy, compressing the feature space toward the label space.
Meanwhile, the use of DenseFlipout enables the model to
learn a posterior distribution over weights instead of point
estimates, thereby producing a Bayesian representation with
quantifiable uncertainty.
The resulting extracted representation is defined as:
```
```
Zsng= GELU
```
## 

```
Flip 32
```
## 

## GELU

## 

```
Flip 64 (GELU(Flip 128 (Isngt )))
```
## 

## (8)

```
2) Normalization
This representation is then normalized through a normaliza-
tion layer to stabilize the Bayesian feature distribution:
```
```
Hsng= Nrm(Zsng) (9)
```
```
3) Prediction
Next, Hsngis split into four parallel sub-branches. Each
sub-branch passes through a Dense layer with two linear
units to map directly into the label space. A softmax layer
then generates the probabilistic output distribution for binary
labels. The final output of this branch is obtained as the
ensemble mean across the four sub-branches:
```
```
ˆsngp =
```
## 1

## 4

## X^4

```
j=
```
```
Softmax
```
## 

```
Dense(j) 2 (Hsng)
```
## 

## (10)

```
D. SOFTWARE DEFECT RISK INFERENCE BLOCK
The defect risk inference block comprises two layers: (i) an
uncertainty-weighted fusion layer, which combines the prob-
abilistic outputs of the two learning branches and calibrates
their contributions based on predictive confidence; and (ii) a
final prediction layer, which transforms the fused probability
into a binary defect risk classification.
```
```
1) Uncertainty-weighted fusion layer
The overall idea is to use the uncertainty levels of the two
branches to adaptively adjust their contribution during fusion,
so that the branch with higher confidence has a stronger
influence on the final prediction. To implement this idea, the
layer fuses the probabilistic outputs from the two learning
blocks, ˆtmpp and ˆsngp , according to their uncertainty levels
under two calibration modes, with the weighting coefficients
determined by either continuous or risk-matrix schemes.
```

a: Calibration modes
The fusion layer operates in one of two modes, depending
on whether uncertainty quantification is required for the final
prediction.

- Label-only prediction: In this mode, a single determin-
    istic forward pass is performed for the temporal branch,
    yielding the prediction ˆtmpp and ˆsngp.
- Prediction with uncertainty quantification: When
    predictive uncertainty is required, the Bayesian capabili-
    ties of both branches are utilized to generate a prediction
    and an uncertainty score for each.
    For the temporal branch, Monte Carlo sampling with T
    stochastic forward passes is performed to obtain a mean
    prediction and its corresponding variance:

```
̄tmpp =
```
## 1

## T

## XT

```
i=
```
```
ˆ(tmppi),σ^2 tmp= Var
```
## 

```
{ ˆ(tmppi) }Ti=
```
## 

## (11)

```
The resulting mean prediction used for fusion is ̄tmpp ,
and its uncertainty is utmp= σ^2 tmp.
The synergy branch is an inherently Bayesian network.
A single forward pass is therefore sufficient to yield
both its probabilistic prediction, denoted as ˆsngp , and
its associated uncertainty, denoted as usng.
```
The final fused prediction, ˆfinalp , is obtained by combining
the branch outputs using weights derived from their uncer-
tainty levels.

b: Weighting schemes
The weights ( ̃wtmp, ̃wsng) are determined using an
uncertainty-weighting mechanism, which can be imple-
mented with either a continuous or a discrete scheme.

- Continuous uncertainty weighting: In the continuous
    variant, the confidence scores are calculated as the in-
    verse of the predictive uncertainty:

```
ctmp=
```
## 1

```
utmp+ ε
```
```
, csng=
```
## 1

```
usng+ ε
```
## , (12)

```
where ε is a small constant to prevent division by zero.
The normalized weights are computed as:
```
```
̃wtmp=
```
```
ctmp
ctmp+ csng
```
```
, ̃wsng=
```
```
csng
ctmp+ csng
```
## (13)

```
The final prediction is then calculated by combining the
branch outputs using these normalized weights.
For the label-only mode, ˆtmpp is used:
```
```
ˆfinalp = ̃wtmpˆtmpp + ̃wsngˆpsng (14)
```
```
For the mode with uncertainty quantification, the mean
prediction ̄tmpp is used instead:
```
```
ˆfinalp = ̃wtmp ̄tmpp + ̃wsngˆpsng (15)
```
- Risk-matrix uncertainty weighting In this variant, the
    fusion mechanism is represented as a two-dimensional
    matrix, where regions in the (ctmp,csng) plane corre-
    spond to different reliability scenarios, each associated

```
with a fixed pair of weights. The confidence levels ctmp
and csngare compared against a threshold τ , which is
estimated from the training set based on the distribution
of confidence scores— for instance, using the median:
```
```
τ = median
```
## 

```
{c(tmpn),c(sngn)}Nn=
```
## 

## , (16)

```
where N denotes the number of training samples.
The discrete weighting rule is then defined as:
```
```
( ̃wtmp, ̃wsng) =
```
## 

## 

## 

## 

## 

## 

## 

## 

## 

```
(1. 0 , 0 .0), ctmp≫ τ, csng≪ τ
(0. 75 , 0 .25), ctmp> τ, csng< τ
(0. 5 , 0 .5), ctmp≥ τ, csng≥ τ
(0. 25 , 0 .75), ctmp< τ, csng> τ
(0. 0 , 1 .0), ctmp≪ τ, csng≫ τ
(17)
Here, ≫ and ≪ denote a significant deviation from τ ,
which can be practically implemented as τ ± δ, where
δ is a tolerance margin (e.g., a multiple of the standard
deviation of c).
The final prediction remains the same:
ˆpfinal= ̃wtmpˆtmpp + ̃wsngˆsngp (18)
```
```
2) Final prediction layer
The ˆpfinal, is passed through a Dense layer with two units
(linear activation), followed by a Softmax layer to produce a
probability distribution over the binary label space:
```
```
ˆ = Softmax(Densey 2 ( ˆpfinal)) (19)
```
```
Here, ˆ ∈y R^2 denotes the final predicted probability vector
of the model, corresponding to the binary classification task
(risk vs. no risk).
```
```
V. EXPERIMENTATION
A. DATASET OVERVIEW
To evaluate our proposed uncertainty-aware defect risk pre-
diction approach, we conduct experiments on a large-scale
dataset of CI/CD builds from open-source software projects.
We adopt and extend the dataset originally constructed by [8].
This dataset provides comprehensive coverage of DevOps
artifacts and build outcomes across diverse projects (with
892,193 builds across 1,689 projects). Projects span various
programming languages (Python, JavaScript, Java, Go, Ruby,
etc.), application domains (web services, data processing,
infrastructure tools, machine learning frameworks), and or-
ganizational contexts (individual maintainers, small teams,
large community-driven projects). Build outcomes are im-
balanced with successful builds significantly outnumbering
failed builds. The temporal span of eight years captures
projects at different lifecycle stages, from early develop-
ment with frequent breaking changes to mature maintenance
phases with stable quality.
The dataset provides a rich set of features capturing vari-
ous aspects of the CI/CD process, which we systematically
map to our four-stream artifact data source. Four tables ??
```

?? ?? ?? presents the mapping between dataset features and
artifact streams, along with feature descriptions.

Follow the strategies described in Section 4.1 of our
architecture description. Continuous features undergo stan-
dardization within each project to achieve zero mean and
unit variance, enabling the model to learn relative patterns
that generalize across projects of different scales. Temporal
features (day of week, hour of day) undergo trigonometric
encoding to preserve cyclic continuity. Categorical features
with low cardinality (e.g., primary language) undergo one-
hot encoding, while high-cardinality features (e.g., author
names) undergo target encoding where each category is re-
placed by the mean target value for that category, smoothed
with global mean to prevent overfitting on rare categories.

```
VI. CONCLUSION
```
We studied uncertainty-aware defect risk prediction for
CI/CD builds and asked whether a two-branch fusion of
temporal evolution and cross–artifact signals, equipped with
Bayesian uncertainty quantification and post-hoc calibration,
can outperform single-branch baselines at low false-positive
budgets and remain reliable under distribution shift. Using
large-scale build- and project-level datasets and four orthog-
onal evaluation slices (Language group, Number/Percentage
of prior builds, Time of day), we evaluated five configurations
(within, leave-one-out, leave-two-out, imbalanced-train, nov-
elty/OOD) per model family.

The results support our research question: two-branch
fusion with UQ and calibration provides more reliable low-
FPR detection than single branches, and retains practical per-
formance under distribution shift. Across scenario and con-
figurations, our two-branch approach consistently matches
or exceeds temporal-only (LSTM) and cross–artifact-only
(MLP) baselines in recall at strict operating points (R@1%
FPR), while achieving better-calibrated probabilities (lower
ECE) and strong practical utility (higher F/100). Benefits are
most pronounced in OOD settings (novelty and leave-one-
out), where fusion plus UQ reduces degradation relative to
the within-ID baseline (smaller ∆R@1%). Calibration fur-
ther improves probability trustworthiness without sacrificing
detection quality. We also report per-slice best configurations
to respect page limits, with full ablations provided elsewhere.
Practically, the method is easy to deploy: thresholds are
tuned once on validation for a target FPR budget and then
fixed for test/production, enabling predictable alert volumes
for engineering triage.

Our study uses OSS CI/CD data and binary build out-
comes; generalization to proprietary ecosystems, alternative
failure taxonomies, or different CI orchestrators may require
retraining and recalibration. Some slices can be imbalanced
or sparse, and leave-two-out may under-represent rare strata.

We plan to (i) explore online recalibration and drift-
aware thresholding, (ii) integrate cost-sensitive objectives to
reflect heterogeneous failure impacts, (iii) extend UQ with
deeper Bayesian ensembling, and (iv) investigate causal and

```
developer-in-the-loop signals to further harden OOD robust-
ness.
```
```
REFERENCES
[1] A. Mockus and D. M. Weiss, “Predicting risk of software changes,” Bell
Labs Technical Journal, vol. 5, no. 2, pp. 169–180, 2000.
[2] N. Nagappan and T. Ball, “Use of relative code churn measures to predict
system defect density,” in Proceedings of the 27th international conference
on Software engineering, 2005, pp. 284–292.
[3] E. Giger, M. Pinzger, and H. C. Gall, “Comparing fine-grained source
code changes and code churn for bug prediction,” in Proceedings of the
8th working conference on mining software repositories, 2011, pp. 83–92.
[4] T. Fukushima, Y. Kamei, S. McIntosh, K. Yamashita, and N. Ubayashi,
“An empirical study of just-in-time defect prediction using cross-project
models,” in Proceedings of the 11th working conference on mining soft-
ware repositories, 2014, pp. 172–181.
[5] Y. Kamei, T. Fukushima, S. McIntosh, K. Yamashita, N. Ubayashi, and
A. E. Hassan, “Studying just-in-time defect prediction using cross-project
models,” Empirical Software Engineering, vol. 21, no. 5, pp. 2072–2106,
2016.
[6] Y. Jiang, B. Shen, and X. Gu, “Just-in-time software defect prediction
via bi-modal change representation learning,” Journal of Systems and
Software, vol. 219, p. 112253, 2025.
[7] K. Al-Sabbagh, M. Staron, and R. Hebig, “Predicting build outcomes in
continuous integration using textual analysis of source code commits,” in
Proceedings of the 18th International Conference on Predictive Models
and Data Analytics in Software Engineering, 2022, pp. 42–51.
[8] A. Kola-Olawuyi, N. R. Weeraddana, and M. Nagappan, “The impact of
code ownership of devops artefacts on the outcome of devops ci builds,”
in Proceedings of the 21st International Conference on Mining Software
Repositories, 2024, pp. 543–555.
[9] R. B. Bahaweres, A. Zulfikar, I. Hermadi, A. I. Suroso, and Y. Arkeman,
“Docker and kubernetes pipeline for devops software defect prediction
with mlops approach,” in 2022 2nd International Seminar on Machine
Learning, Optimization, and Data Science (ISMODE). IEEE, 2022, pp.
248–253.
[10] S. Dalla Palma, D. Di Nucci, F. Palomba, and D. A. Tamburri, “Within-
project defect prediction of infrastructure-as-code using product and pro-
cess metrics,” IEEE Transactions on Software Engineering, vol. 48, no. 6,
pp. 2086–2104, 2021.
[11] L. Giorgio, M. Nicola, S. Fabio, and S. Andrea, “Continuous defect
prediction in ci/cd pipelines: A machine learning-based framework,” in In-
ternational Conference of the Italian Association for Artificial Intelligence.
Springer, 2021, pp. 591–606.
[12] N. E. Fenton and M. Neil, “A critique of software defect prediction
models,” IEEE Transactions on software engineering, vol. 25, no. 5, pp.
675–689, 2002.
[13] M. Ali, T. Mazhar, Y. Arif, S. Al-Otaibi, Y. Y. Ghadi, T. Shahzad, M. A.
Khan, and H. Hamam, “Software defect prediction using an intelligent
ensemble-based model,” IEEe Access, vol. 12, pp. 20 376–20 395, 2024.
[14] I. H. Laradji, M. Alshayeb, and L. Ghouti, “Software defect prediction
using ensemble learning on selected features,” Information and Software
Technology, vol. 58, pp. 388–402, 2015.
[15] T. Hoang, H. K. Dam, Y. Kamei, D. Lo, and N. Ubayashi, “Deepjit: an
end-to-end deep learning framework for just-in-time defect prediction,”
in 2019 IEEE/ACM 16th International Conference on Mining Software
Repositories (MSR). IEEE, 2019, pp. 34–45.
[16] T. Hoang, H. J. Kang, D. Lo, and J. Lawall, “Cc2vec: Distributed rep-
resentations of code changes,” in Proceedings of the ACM/IEEE 42nd
international conference on software engineering, 2020, pp. 518–529.
[17] G. Giray, K. E. Bennin, Ö. Köksal, Ö. Babur, and B. Tekinerdogan, “On
the use of deep learning in software defect prediction,” Journal of Systems
and Software, vol. 195, p. 111537, 2023.
[18] F. Khosravi, M. Müller, M. Glaß, and J. Teich, “Uncertainty-aware relia-
bility analysis and optimization,” in 2015 Design, Automation & Test in
Europe Conference & Exhibition (DATE). IEEE, 2015, pp. 97–102.
[19] Y. Gal and Z. Ghahramani, “Dropout as a bayesian approximation: Rep-
resenting model uncertainty in deep learning,” in international conference
on machine learning. PMLR, 2016, pp. 1050–1059.
[20] J. Ren, J. Wen, Z. Zhao, R. Yan, X. Chen, and A. K. Nandi, “Uncertainty-
aware deep learning: A promising tool for trustworthy fault diagnosis,”
IEEE/CAA Journal of Automatica Sinica, vol. 11, no. 6, pp. 1317–1330,
2024.
```

[21] R. Grewal, P. Tonella, and A. Stocco, “Predicting safety misbehaviours
in autonomous driving systems using uncertainty quantification,” in 2024
IEEE Conference on Software Testing, Verification and Validation (ICST).
IEEE, 2024, pp. 70–81.

```
THI-HUONG-GIANG VU She is a senior lec-
turer at the School of Information and Commu-
nication Technology, Hanoi University of Science
and Technology. She received the Ph.D. degree in
Information Technology in 2010 from Grenoble
INP, France. Her research focuses on software
project management and non-functional require-
ments, such as security and risk management,
contributing to both academia and industry.
```
```
MANH-TUAN NGUYEN
```
```
VAN-DUY PHAN
```

