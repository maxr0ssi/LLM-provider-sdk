

Role: You are an super full stack developer
Task: you are handling the refactoring of an entire repo. Taking a behemoth repo into one mono repo and 2 private independent PyPI packages.


Outline:
** for reference I am only expecting us to complete stage 1 in this interaction, the remaining stages are so the infrastructure plan is clear and will help guide decision making**

(note for now use Steer directory .venv)
Stage 1

Part 1: Research 
Begin by extensively researching the Steer/ directory. Your job is to analyse the flows from Fast API to the usage of LLMs and the LLM rubric.

Part 2:
Divide a list that separates Steer/ , the LLM Providers API component and its normalisation, the LLM Rubric parameters. 


Part 3: 
Using this dir LLM-provider-sdk, you will COPY (use terminal) the LLM provider related directories and files.
This involves only files related directly to utilising the external LLM apis and its normalisation and validation.

Part 4:
Adjust the copied files, restructure the new repo and then add main.py files. Then, convert this into a private PyPI registry. 
Generate PyPi Specific unit tests note again we can COPY most of the code from mono repo and adjust imports.


Part 5: 
100% unit test pass


———
Stage 2: 
** This is not for current implementation this for context so you can see where we are going**

Part 1 
Analogous logic to Stage 1 part 1, except this time we shall focus on LLM Rubric specific logic.

Part 2:
Using our list of LLM Rubric files, we shall COPY these files into a new repo called SteerOrchastrator

Part 3: 
analogous logic to stage 1, we want to turn this into a private PyPi Registry. Adjust code, structure and add main files. LLM-provider-sdk should be a dependency.

Part4:
In addition we will need to integrate our sdk into our LLM to handle input calls, I.e, when a user enters a prompt it goes through orchestrator straight into sdk (via orchestrator) but we don’t apply any direct orchestrator logic here, but then the sdk returns a result which does have scoring logic applied to it.

Part 5: 
Create PyPi Specific Unit tests — note again we can COPY most of the code from mono repo and adjust imports.

Part 6: 
Finalise package 


——-

Stage 3
*the final hurdle*

Part 1:
Return to main mono repo. Update dependencies to use SteerOchastrator.

Part2;
Rename all files related to LLM-provider-sdk and SteerOrchastrator (prefix with OLD)

Part3:
Hook up all APIs to now direct to Packages and remove links to all old mono repo logic that is covered by packages. 

Note: we should only be dependent on SteerOrchastor as everything is handled inside that independent package.


Part: 4
New unit tests for handling interactions between packages in mono repo.  

Part 5:
100% unit test pass rate




 
