# Easy MCF - Release Roadmap

## Scope

Easy MCF is a platform to streamline the job search and application process for job seekers in Singapore using [MyCareerFutures](http://mycareersfuture.gov.sg/) website

An early prototype version `jobsearch` is available for reference in the repo `jobsearch/` with webscraping methods developed in python for automating the search and application process using `selenium` for python package.  


| repo        | version   | description             |
| ----------- | --------- | ----------------------- |
| jobsearch   | 20250705  | prototype local         |
| easymcf     | 010       | POC local               |
| easymcf     | 020       | MVP cloud               |
| easymcf     | 100       | Beta single user        |  

__features__

| id | feature              | prototype local    | poc local       | mvp cloud        | beta single user        |
| -- | -------------------- | ------------------ | --------------- | ---------------- | ----------------------- |
| 01 | be runtime           | python             | python          | python           | python                  |
| 02 | fe runtime           | google sheets      | angular js      | angular js       | angular js              |
| 03 | database             | sqlite + gs        | sqlite          | aws sql          | aws sql                 |
| 04 | be deploy            | local              | local           | aws api gateway  | aws api gateway         |
| 05 | fe deploy            | google sheets      | local           | aws ec2          | aws ec2                 |
| 06 | search by keywords   | yes                | yes             | yes              | yes                     |
| 07 | crm pipeline         | yes                | yes             | yes              | yes                     |
| 08 | automated apply      | yes                | yes             | yes              | yes                     |
| 09 | match algorithm      | primitive + salry  | primitive title | semantic desc    | semantic desc                    |

__learning from mcfpipe__

`easymcf` has similar aims as the reference `mcfpipe` to improve on the prototype `jobsearch`, with similarities and differences by features:

_mcf goals_

improve on the prototype in the following areas:

| id | feature                                     | mcfpipe | easymcf | 
| -- | ------------------------------------------- | ------- | ------- | 
| 01 | deploy to cloud aws                         | yes     | yes     | 
| 02 | backend api                                 | yes     | yes     | 
| 03 | front end not gs                            | yes     | yes     | 
| 04 | multiple users                              | yes     | yes     | 
| 05 | serverless infrastructure                   | yes     | no      | 
| 06 | no-sql database                             | yes     | no      | 
| 07 | private endpoints                           | yes     | no      | 
| 08 | re-usable AWS ias infrastructure            | yes     | no      | 
| 09 | fully automated cid                         | yes     | no      | 

_learning from experience_

the experience from the `mcfpipe` was a high upfront investment in cloud infrastructure, CICD automation, without any workable MVP.  The aim of the `easymcf` is to learn from this experience, still leveraging on the POC demonstated from the prototype. 

Additionally, the serverless infrastructure and no-sql database for the job search function, aiming to minimize cloud compute costs, over-complicated the design and added another barrier to MVP and front-end development.

## requirements

See [010-01-requirements.md](010/010-01-requirements.md) for the detailed requirements for release `010` (POC local).