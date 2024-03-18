@echo off
set batchdir=%~dp0%
%batchdir:~0,2%
cd %batchdir%
python "TestReturns.py"