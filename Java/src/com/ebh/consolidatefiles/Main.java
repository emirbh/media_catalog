package com.ebh.consolidatefiles;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.attribute.BasicFileAttributes;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import com.fasterxml.jackson.core.type.TypeReference;
import org.apache.commons.io.FileUtils;
import org.apache.commons.io.FilenameUtils;
import com.fasterxml.jackson.databind.ObjectMapper;

import static java.util.Collections.singletonList;
import static org.apache.commons.codec.digest.DigestUtils.md5Hex;

public class Main {
    final private static String REPOSITORY = "repository.json";

    private static Stream<String> getFiles(String dir) {
        try {
            return Files.list(Paths.get(dir))
                    .flatMap(path -> path.toFile().isDirectory() ?
                            getFiles(path.toFile().toString()) : singletonList(path.toFile().toString()).stream());
        } catch(Exception e) {
            System.out.println(e);
        }
        return null;
    }

    private static String getUniqueContent(String path) {
        try {
            FileInputStream fis = new FileInputStream(Paths.get(path).toFile());
            String md5 = md5Hex(fis);
            fis.close();
            return md5;
        } catch(IOException e) {
            System.out.println(e);
        }
        return null;
    }

    private static String storeUnique(String outputFolder, String sourcePath, DateFormat dateFormat,
                                      HashMap<String, Integer> counts) {
        try {
            BasicFileAttributes attr       = Files.readAttributes(Paths.get(sourcePath), BasicFileAttributes.class);
            String              date       = dateFormat.format(attr.creationTime().toMillis());
            counts.putIfAbsent(date, 0);
            String              targetPath = outputFolder+"/" +
                                             date + "_" + String.valueOf(counts.get(date) + 1) +
//                                           "-" + sourcePath.getFileName()));
                                             "." + FilenameUtils.getExtension(sourcePath);
            counts.put(date, counts.get(date) + 1);
            FileUtils.copyFile(new File(sourcePath), new File(targetPath));
            System.out.println(sourcePath);
            return targetPath;
        } catch(IOException e) {
            System.out.println(e);
        }
        return null;
    }

    private static void saveRepository(Map<String, List<String>> map, String repositoryPath) {
        try {
            new ObjectMapper().writeValue(new FileOutputStream(repositoryPath), map);
        } catch(Exception ex) {
            System.out.println(ex);
        }
    }

    private static Map<String, List<String>> getRepository(String repositoryPath) {
        try {
            return new ObjectMapper().readValue(new FileInputStream(repositoryPath), new TypeReference<Map<String, List<String>>>() {});
        } catch(Exception ex) {
            System.out.println(ex);
        }
        return new HashMap<>();
    }

    public static void main(String[] args) {
        final String     imageRegex = "([^\\s]+(\\.(?i)(jpg|jpeg|png|gif|bmp))$)";
        final String     movieRegex = "([^\\s]+(\\.(?i)(mp4|mov))$)";
        final DateFormat dateFormat = new SimpleDateFormat("yyyyMMdd");
        final Pattern    matchEntry = Pattern.compile(CliArguments.getInstance(args).getFilter());

        try {
            Map<String, List<String>> repository = getRepository(REPOSITORY);
            HashMap<String, Integer>  counts     = new HashMap<>();
            repository.forEach((uid, items) -> counts.put(uid, items.size()));

            getFiles(CliArguments.getInstance(args).getInputFolder())
                .filter(item -> matchEntry.matcher(item).matches())
                .collect(Collectors.groupingBy(Main::getUniqueContent))
                .forEach((uid, items) -> {
                            repository.putIfAbsent(uid, new ArrayList<>());
                            String targetPath = storeUnique(CliArguments.getInstance(args).getOutputFolder(), items.get(0), dateFormat, counts);
                            if (repository.get(uid).get(0).compareTo(targetPath) != 0) {
                                repository.get(uid).add(0, targetPath);
                            }
                        });
            saveRepository(repository, REPOSITORY);
        } catch (Exception e) {
            System.out.println(e.getMessage());
        }
    }
}

