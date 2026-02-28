package com.ebh.consolidatefiles;

import org.apache.commons.cli.*;

public class CliArguments {
    private static final CliArguments INSTANCE = new CliArguments();

    private static final String OPTION_INPUT  = "input";
    private static final String OPTION_OUTPUT = "output";
    private static final String OPTION_FILTER = "filter";

    private CommandLine commandLine;

    private CliArguments() {}

    public static CliArguments getCliArguments() { return INSTANCE; }

    public String getInputFolder() { return commandLine.getOptionValue(OPTION_INPUT); }
    public String getOutputFolder() {
        return commandLine.getOptionValue(OPTION_OUTPUT);
    }
    public String getFilter() { return commandLine.getOptionValue(OPTION_FILTER); }

    public static CliArguments getInstance(String[] args) {
        if(INSTANCE.commandLine != null) {
            return INSTANCE;
        }
        Options options = new Options();

        Option optionInput = new Option("i", CliArguments.OPTION_INPUT, true,
                "Directory with files to be consolidated");
        optionInput.setRequired(false);
        options.addOption(optionInput);

        Option optionOutput = new Option("o", CliArguments.OPTION_OUTPUT, true,
                "Directory with consolidated files");
        optionOutput.setRequired(false);
        options.addOption(optionOutput);

        Option optionFilter = new Option("f", CliArguments.OPTION_FILTER, true,
                "File name filter, for example '*.jpeg'");
        optionFilter.setRequired(false);
        options.addOption(optionFilter);

        CommandLineParser parser = new DefaultParser();
        HelpFormatter formatter = new HelpFormatter();
        CommandLine cmd = null;

        try {
            cmd = parser.parse(options, args);
        } catch (ParseException e) {
            System.out.println(e.getMessage());
            formatter.printHelp("utility-name", options);

            System.exit(1);
        }

        INSTANCE.commandLine = cmd;

        return INSTANCE;
    }
}

